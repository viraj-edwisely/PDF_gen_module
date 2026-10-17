"""Generation pipeline: one run_topic -> content JSON -> PDF.

Every model step is saved in the `steps` table, so an interrupted run resumes without paying again. Each reply is tidied
and checked (content.py); only the broken items go back to the model, once; what is still broken is left out, with a warning.
GATE: context -> PYQs -> plan -> notes (two calls) and questions, at the same time -> second check of the answer keys -> PDF.
Non-GATE: context -> plan -> topics (three per call, at the same time) -> case study, practice and revision -> PDF.
"""
import functools, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
import content as C, db, llm, pyq, retrieve
from config import PARALLEL, PROVIDERS, VERIFY_PROVIDER, secret

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = C.RENDER
UNCHECKED_NOTE = 'Answer keys were not re-checked by a second model: check them before publishing.'
REPAIR_TOKENS = 32_000    # a repair rewrites a few items: a longer reply means the model has lost its way
RETRY = '\n\nYour previous reply could not be used: {problems}\nReturn the complete JSON again, in exactly the format asked for.'


def same_kind(old, new):
    """A fix must have the shape of the item it replaces (a block stays an object, a list a list), never JSON written as text."""
    if old is None: return isinstance(new, (dict, list))
    return isinstance(new, dict) if isinstance(old, dict) else isinstance(new, list) if isinstance(old, list) else not isinstance(new, (dict, list))


class CapReached(Exception): pass
class Cancelled(Exception): pass


def read(path):
    return open(os.path.join(HERE, 'prompts', path), encoding='utf-8').read()


def fill(template, **values):
    """Replace {{NAME}} in one pass, so text inside a value (book text) is never treated as a placeholder."""
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(values.get(m.group(1), m.group(0))), template)


@functools.cache
def figure_reference():
    """The exact spec of every figure kind, generated from the figure code (run in a subprocess: no matplotlib here)."""
    r = subprocess.run([sys.executable, os.path.join(RENDER, 'figures.py'), '--reference'], capture_output=True, timeout=120)
    return r.stdout.decode('utf-8')


def system_prompt(mode):
    shared = dict(MATHS=read('maths.md'), FIGURES=read('figure_catalogue.md') + '\n\n## Exact spec of each kind\n\n' + figure_reference())
    if mode == 'gate':
        return fill(read('gate/system.md'), STANDARD=read('gate/gate_level_standard.md'), SCHEMA=read('gate/content_schema.md'), **shared)
    example = open(os.path.join(RENDER, 'example_nongate.json'), encoding='utf-8').read()
    return fill(read('nongate/system.md'), SCHEMA=read('nongate/content_schema.md'), EXAMPLE=example, **shared)


def log(run_id, rt_id, text):
    db.sql('insert into logs (run_id, run_topic_id, text) values (%s,%s,%s)', (run_id, rt_id, text[:500]))


class Job:
    """One run_topic being processed: saved steps, model calls with tidy/check/repair, warnings, progress, cost cap."""

    def __init__(self, rt, run):
        self.rt, self.run, self.provider = rt, run, run['provider']
        self.system = system_prompt(run['mode'])
        self.feedback = (run['options'] or {}).get('feedback')

    def _guard(self):
        if db.sql('select status from runs where id=%s', (self.run['id'],))[0]['status'] == 'cancelled': raise Cancelled()

    def log(self, text): log(self.run['id'], self.rt['id'], text)

    def progress(self, text):
        self.log(text)
        db.sql('update run_topics set step=%s where id=%s', (text, self.rt['id']))
        db.sql('update runs set heartbeat_at=now() where id=%s', (self.run['id'],))

    def warn(self, text):
        self.log('⚠ ' + text)
        db.sql('update run_topics set warnings = warnings || to_jsonb(%s::text) where id=%s', (text, self.rt['id']))

    def saved(self, name):
        rows = db.sql('select output from steps where run_topic_id=%s and name=%s', (self.rt['id'], name))
        return rows[0]['output'] if rows else None

    def charge(self, usage, name):
        """Add the cost of a model call to the topic, the run and the usage history; stop the run at its cap."""
        if not usage['cost']: return
        db.event(self.run['created_by'], 'model call', self.run['id'], usage['cost'], topic=self.rt['name'], step=name,
                 provider=self.provider, model=PROVIDERS[self.provider]['model'], input_tokens=usage['in'], output_tokens=usage['out'])
        db.sql('update run_topics set cost_usd = cost_usd + %s where id=%s', (usage['cost'], self.rt['id']))
        run = db.sql('update runs set cost_usd = cost_usd + %s, heartbeat_at=now() where id=%s returning cost_usd, cost_cap', (usage['cost'], self.run['id']))[0]
        if run['cost_usd'] >= run['cost_cap']: raise CapReached()

    def save(self, name, output, usage):
        db.sql('insert into steps (run_topic_id, name, output, input_tokens, output_tokens, cost_usd) values (%s,%s,%s::jsonb,%s,%s,%s) '
               'on conflict (run_topic_id, name) do update set output=excluded.output, input_tokens=excluded.input_tokens, '
               'output_tokens=excluded.output_tokens, cost_usd=excluded.cost_usd', (self.rt['id'], name, json.dumps(output), usage['in'], usage['out'], usage['cost']))
        self.charge(usage, name)

    def step(self, name, fn):
        """A step that makes no model call of its own. Runs once; the output is saved."""
        self._guard()
        out = self.saved(name)
        if out is None:
            self.log(f'{name}: working')
            out = fn()
            self.save(name, out, {'in': 0, 'out': 0, 'cost': 0})
        return out

    def _call(self, prompt, usage, provider=None, max_tokens=None):
        out, u, raw = llm.generate_json(provider or self.provider, self.system, prompt, max_tokens)
        for k in usage: usage[k] += u[k]
        return out, raw

    def _repair(self, name, out, probs, tidy, usage, provider=None):
        """Send only the problem items back, with their problems, and merge the fixes in. One call."""
        by_path = {}
        for p, m, _ in probs: by_path.setdefault(p, []).append(m)
        def current(p):
            try: return C.get(out, p)
            except (KeyError, IndexError, TypeError): return None
        items = [{'ref': C.ref(p), 'problems': ms, 'current': current(p)} for p, ms in by_path.items()]
        self.log(f'{name}: sending {len(items)} item(s) back for repair: ' + '; '.join(f"{C.label(p, out)}: {ms[0][:80]}" for p, ms in list(by_path.items())[:3]))
        try: reply, _ = self._call(fill(read('repair.md'), ITEMS=json.dumps(items, ensure_ascii=False)), usage, provider, REPAIR_TOKENS)
        except llm.LLMError as e: self.log(f'{name}: the repair call failed: {e}'); return out
        for f in (reply.get('fixes') if isinstance(reply, dict) else None) or []:
            p = C.unref(f.get('ref', '')) if isinstance(f, dict) else None
            if p in by_path and 'value' in f and same_kind(current(p), f['value']):
                try: C.put(out, p, f['value'])
                except (KeyError, IndexError, TypeError): pass
        return tidy(out)

    def _settle(self, name, out, probs, warn_soft=True):
        """Leave out what is still broken; warn about requirements that are still not met."""
        hard = [(p, m) for p, m, h in probs if h and p]
        if hard:
            names = [f'{C.label(p, out)} ({m[:90]})' for p, m in hard[:4]]
            C.drop(out, [p for p, _ in hard])
            self.warn(f'{len(hard)} item(s) were left out because they were still broken after a repair: ' + '; '.join(names) + (' ...' if len(hard) > 4 else ''))
        if warn_soft:
            for p, m, h in probs:
                if not h: self.warn(f'{C.label(p, out)}: {m[:200]}')

    def ask(self, name, user, tidy=lambda o: o, problems=lambda o: [], provider=None):
        """One model step: call, tidy, check; a reply that is unusable as a whole is asked for once more; broken items
        go back for one repair; what is still broken is left out. The result is saved, so Resume never pays twice."""
        self._guard()
        out = self.saved(name)
        if out is not None: self.log(f'{name}: reused from an earlier attempt (no cost)'); return out
        if self.feedback: user += f'\n\nExtra instructions from the user for this PDF: {self.feedback}'
        usage, out, raw, probs = {'in': 0, 'out': 0, 'cost': 0.0}, None, '', []
        for attempt in range(2):
            try:
                out, raw = self._call(user if not attempt else user + RETRY.format(problems='; '.join(m for _, m, _ in probs[:4])), usage, provider)
                out = tidy(out); probs = problems(out)
            except llm.LLMError as e:
                out, raw, probs = None, e.raw or raw, [((), str(e), True)]
            whole = [m for p, m, h in probs if not p and h]
            if out is not None and not whole: break
            self.log(f'{name}: the reply could not be used, asking again: {whole[0][:200]}')
        if out is None or any(not p and h for p, _, h in probs):
            db.sql('insert into steps (run_topic_id, name, output, cost_usd) values (%s,%s,%s::jsonb,%s) on conflict (run_topic_id, name) do update set output=excluded.output',
                   (self.rt['id'], name + '_failed', json.dumps({'raw': raw[:200_000], 'problems': [m for _, m, _ in probs]}), usage['cost']))
            self.charge(usage, name + '_failed')
            raise llm.LLMError(f'the model could not produce a usable "{name}" part: ' + '; '.join(m for _, m, _ in probs[:2]))
        items = [x for x in probs if x[0]]
        if items:
            out = self._repair(name, out, items, tidy, usage, provider)
            probs = problems(out)
        self._settle(name, out, probs)
        self.save(name, out, usage)
        self.log(f'{name}: done ({usage["in"]} tokens in, {usage["out"]} out, ${usage["cost"]:.3f})')
        return out

    def revise(self, name, obj, probs, tidy, problems, describe=lambda out: None, provider=None):
        """A saved step that repairs given items of an existing object (used after the second check of the answers).
        describe(repaired) reports the changes before anything broken is left out."""
        self._guard()
        out = self.saved(name)
        if out is not None: return out
        usage = {'in': 0, 'out': 0, 'cost': 0.0}
        out = self._repair(name, json.loads(json.dumps(obj)), probs, tidy, usage, provider)
        describe(out)
        self._settle(name, out, [x for x in problems(out) if x[2]], warn_soft=False)
        self.save(name, out, usage)
        return out


# ---------------------------------------------------------------- shared steps
def book_note(found):
    return 'Book material for this topic follows.' if found else 'No book material is available for this topic: write it from your own knowledge.'


def run_book(run):
    """The run's book row, or None when it was started without a book (or the book was deleted since)."""
    rows = db.sql('select * from books where id=%s', (run['book_id'],)) if run['book_id'] else []
    return rows[0] if rows else None


def render_and_store(job, mode, content):
    """Render the PDF in a subprocess, upload PDF and JSON, mark the topic finished."""
    folder = tempfile.mkdtemp(); src, pdf = os.path.join(folder, 'content.json'), os.path.join(folder, 'out.pdf')
    json.dump(content, open(src, 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, os.path.join(RENDER, f'render_{mode}.py'), src, pdf], capture_output=True, text=True, encoding='utf-8', timeout=600)
    if r.returncode: raise RuntimeError('PDF rendering failed: ' + r.stderr[-300:])
    try: report = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): report = {}
    for w in report.get('warnings', [])[:10]: job.warn('In the PDF: ' + w)
    base = f"{job.run['id']}/{job.rt['id']}"
    job.log(f'PDF rendered ({os.path.getsize(pdf) // 1024} KB), uploading')
    db.upload('outputs', base + '.pdf', open(pdf, 'rb').read(), 'application/pdf')
    db.upload('outputs', base + '.json', json.dumps(content, ensure_ascii=False).encode('utf-8'), 'application/json')
    warns = db.sql('select warnings from run_topics where id=%s', (job.rt['id'],))[0]['warnings']
    db.sql("update run_topics set status=%s, step='done', pdf_path=%s, json_path=%s where id=%s", ('warnings' if warns else 'done', base + '.pdf', base + '.json', job.rt['id']))


# ---------------------------------------------------------------- GATE
def pyq_step(job, topic, o):
    """Previous-year questions from this topic's sources (links, or text read from uploaded PDF/Word files on the Generate page);
    only those found verbatim in a source are kept."""
    src = (o.get('pyq') or {}).get(topic) or {}
    texts = list(src.get('texts') or [])
    for url in src.get('urls') or []:
        try: texts.append(pyq.fetch_text(url))
        except Exception as e: job.warn(f'PYQ source could not be read ({url}): {e}')
    if not texts: return []
    prompts = [fill(read('gate/pyq_extract.md'), TOPIC=topic, PAPER=o['paper'], SUBJECT=o['subject'], SOURCE=text[:120_000]) for text in texts]
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        found = [q for out in pool.map(lambda a: job.ask(f'pyq_{a[0]}', a[1], tidy=C.pyq_questions), enumerate(prompts)) for q in out['questions']]
    kept, dropped = pyq.keep_verified(found, texts)
    job.log(f'PYQs: {len(found)} found in {len(texts)} source(s), {len(kept)} verified, {len(dropped)} dropped')
    kept = list({re.sub(r'\W+', '', q['question'].lower())[:80]: q for q in kept}.values())[:8]
    if not kept: job.warn('No previous-year questions on this topic were found in the given sources. The PYQ section is left out.')
    for d in dropped[:3]: job.warn('A previous-year question was ignored: ' + d)
    return kept


def figure_brief(f):
    """A figure as the reviewer sees it: its kind, title, caption and the labels and values it shows."""
    words = [w for w in re.findall(r'"([^"]{1,40})"', json.dumps(f.get('spec') or {}, ensure_ascii=False))
             if w not in ('x', 'y', 'label', 'text', 'curves', 'points', 'nodes', 'edges', 'id', 'fill', 'kind', 'shape', 'color', 'style')]
    return {'kind': f.get('kind'), 'title': f.get('title'), 'caption': f.get('caption'), 'shows': ', '.join(dict.fromkeys(words))[:300],
            'values': [round(v, 4) for v in C._numbers(f.get('spec'))][:40]}


def verify(job, topic, o, notes, q):
    """A second model re-solves every question and worked example and reviews whether examples, figures and questions
    teach; the items it disputes or finds weak go back to the writer once."""
    provider = VERIFY_PROVIDER if secret(PROVIDERS[VERIFY_PROVIDER]['key']) else job.provider
    fields = ('qtype', 'question', 'options', 'answer', 'answer_range', 'solution')
    items = [{'ref': C.ref(('practice', i)), **{k: x.get(k) for k in fields}} for i, x in enumerate(q['practice'])]
    items += [{'ref': C.ref(('sample_paper', 'questions', i)), **{k: x.get(k) for k in fields}} for i, x in enumerate(q['sample_paper']['questions'])]
    for i, n in enumerate(notes):
        for j, b in enumerate(n['blocks']):
            if b.get('type') == 'example':
                figs, rest = C._figures_and_text([b.get('problem'), b.get('solution')])
                items.append({'ref': C.ref(('notes', i, 'blocks', j)), 'section': n['heading'], 'worked_example': rest[:1], 'solution': rest[1:],
                              'figures': [figure_brief(f) for f in figs]})
            elif b.get('type') == 'figure':
                items.append({'ref': C.ref(('notes', i, 'blocks', j)), 'section': n['heading'], 'figure': figure_brief(b)})
    valid = {x['ref'] for x in items}
    keep = lambda out, k: [i for i in (out.get(k) if isinstance(out, dict) else None) or [] if isinstance(i, dict) and i.get('ref') in valid]
    tidy = lambda out: {'issues': keep(out, 'issues'), 'weak': keep(out, 'weak')[:6]}
    found = job.ask('verify', fill(read('gate/verify.md'), TOPIC=topic, PAPER=o['paper'], SUBJECT=o['subject'], ITEMS=json.dumps(items, ensure_ascii=False)),
                    tidy=tidy, provider=provider)
    issues, weak = found['issues'], found.get('weak', [])
    job.log(f'Second check ({provider}): {len(issues)} of {len(items)} items disputed, {len(weak)} found weak')
    if not issues and not weak: return notes, q
    obj = {'notes': notes, **q}
    probs = [(C.unref(i['ref']), f"a second check found a mistake: {str(i.get('problem', ''))[:300]}" + (f" (it gets: {i['correct']})" if i.get('correct') else ''), False) for i in issues]
    probs += [(C.unref(w['ref']), f"a quality review found this item does not teach well: {str(w.get('problem', ''))[:300]}. Rewrite it to fix that, keeping it correct", False)
              for w in weak if w['ref'] not in {i['ref'] for i in issues}]
    def describe(fixed):
        for i in issues:
            p = C.unref(i['ref'])
            try: before, after = C.get(obj, p), C.get(fixed, p)
            except (KeyError, IndexError, TypeError): continue
            why = str(i.get('problem', ''))[:140]
            if p[0] == 'notes': job.warn(f'{C.label(p, fixed)}: the worked example was revised after a second check found a mistake ({why}). Please review it.')
            elif before.get('answer') != after.get('answer'): job.warn(f"{C.label(p)}: answer changed from {before.get('answer')} to {after.get('answer')} after a second check. Please review it.")
            else: job.warn(f"{C.label(p)}: a second check disagreed ({why}), but the writer kept the answer {after.get('answer')}. Please check it.")
        for w in weak:
            p = C.unref(w['ref'])
            try: changed = C.get(obj, p) != C.get(fixed, p)
            except (KeyError, IndexError, TypeError): continue
            job.warn(f"{C.label(p, fixed)}: {'rewritten' if changed else 'kept as it was'} after a quality review ({str(w.get('problem', ''))[:140]}).")
    fixed = job.revise('verify_fix', obj, probs, lambda x: {**C.gate_notes(x), **C.gate_questions(x)}, lambda x: C.gate_questions_problems(x, o['paper']), describe)
    return fixed['notes'], {k: fixed[k] for k in ('practice', 'sample_paper', 'traps', 'revision_card')}


def gate(job):
    run, rt = job.run, job.rt
    o, topic = run['options'], rt['name']
    book = run_book(run)
    job.progress('Reading the book' if book else 'Starting')
    def context():
        ctx = retrieve.topic_context(book, run['scope_start'], run['scope_end'], topic)
        if book and not ctx['found']: job.warn('Topic not found in the chosen book scope: written from the model\'s own knowledge, not grounded in the book.')
        return ctx
    ctx = job.step('context', context)
    book_text, note = (ctx['text'] if ctx['found'] else ''), book_note(ctx['found'])
    job.progress('Previous-year questions')
    pyqs = job.step('pyq', lambda: pyq_step(job, topic, o))
    pyq_brief = '\n'.join('- ' + q['question'][:160] for q in pyqs) or '(none)'
    base = dict(TOPIC=topic, PAPER=o['paper'], SUBJECT=o['subject'], BOOK=book_text, BOOK_NOTE=note, USER_PROMPT=o.get('prompt') or '(none)')

    job.progress('Planning the sections')
    plan = job.ask('plan', fill(read('gate/plan.md'), **base, PYQS=pyq_brief, SYLLABUS=o.get('syllabus_line') or ''), tidy=C.gate_plan, problems=C.gate_plan_problems)
    archetypes = '; '.join(map(str, plan.get('archetypes') or []))

    # three calls depend only on the plan, so they run at the same time: the two halves of the notes, and all the questions
    sections = plan['sections']
    half = (len(sections) + 1) // 2
    groups = [sections[:half], sections[half:]] if len(sections) > 3 else [sections]

    def write_notes(k, group):
        others = ', '.join(s['heading'] for s in sections if s not in group) or '(none)'
        return job.ask(f'notes_part{k}', fill(read('gate/notes.md'), **base, SECTIONS=json.dumps(group, ensure_ascii=False), DONE=others, ARCHETYPES=archetypes),
                       tidy=C.gate_notes, problems=lambda out: C.gate_notes_problems(out, group))['notes']

    job.progress('Writing notes and questions (at the same time)')
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        note_jobs = [pool.submit(write_notes, k, g) for k, g in enumerate(groups)]
        q_job = pool.submit(job.ask, 'questions', fill(read('gate/questions.md'), **base, ARCHETYPES=archetypes, HEADINGS=', '.join(s['heading'] for s in sections), PYQS=pyq_brief),
                            C.gate_questions, lambda out: C.gate_questions_problems(out, o['paper']))
        notes, q = [n for f in note_jobs for n in f.result()], q_job.result()

    if o.get('verify', True):
        job.progress('Second check of the answers')
        notes, q = verify(job, topic, o, notes, q)
    else: job.warn(UNCHECKED_NOTE)

    def assemble():
        c = {'paper': o['paper'], 'subject': o['subject'], 'topic_name': topic, 'syllabus_line': plan.get('syllabus_line', ''), 'subtitle': plan.get('subtitle', ''),
             'objectives': plan['objectives'], 'prerequisites': plan.get('prerequisites', []), 'notes': notes, 'traps': q['traps'], 'revision_card': q['revision_card'],
             'pyqs': pyqs, 'practice': q['practice'], 'sample_paper': q['sample_paper']}
        errors = C.gate_check(c)[0]
        bad = sorted({int(m.group(1)) for e in errors if (m := re.match(r'PYQ(\d+):', e))}, reverse=True)
        for i in bad: del c['pyqs'][i - 1]                      # official questions are dropped, never rewritten
        if bad: job.warn(f'{len(bad)} previous-year question(s) were removed because they did not pass the checks.')
        rest = [e for e in errors if not re.match(r'(PYQ|P|S)\d+:', e)]
        if rest: job.warn('The GATE checker still reports: ' + '; '.join(rest[:4]))
        return c
    job.progress('Assembling')
    content = job.step('content', assemble)
    job.progress('Rendering the PDF')
    render_and_store(job, 'gate', content)


# ---------------------------------------------------------------- Non-GATE
def nongate(job):
    run, rt = job.run, job.rt
    o, names = run['options'], run['options']['topics']
    book = run_book(run)
    job.progress('Reading the book' if book else 'Starting')
    def context():
        ctxs = [retrieve.topic_context(book, run['scope_start'], run['scope_end'], t) for t in names]
        for t, c in zip(names, ctxs):
            if book and not c['found']: job.warn(f'Topic "{t}" not found in the chosen book scope: written from the model\'s own knowledge, not grounded in the book.')
        whole = ctxs[0]['text'] if all(c['whole_scope'] for c in ctxs) else None
        return {'whole': whole, 'per_topic': [c['text'] if c['found'] else '' for c in ctxs], 'found': [c['found'] for c in ctxs]}
    ctx = job.step('context', context)
    base = dict(SUBJECT=o['subject'], USER_PROMPT=o.get('prompt') or '(none: use the standard template)')

    job.progress('Planning the module')
    plan = job.ask('plan', fill(read('nongate/plan.md'), **base, TOPICS='; '.join(names), STUDY_TIME=o.get('study_time') or '', AUDIENCE=o.get('audience') or '',
                                BOOK_NOTE=book_note(any(ctx['found'])), BOOK=ctx['whole'] or '\n\n'.join(ctx['per_topic'])[:160_000]),
                   tidy=C.nongate_plan, problems=C.nongate_plan_problems)

    # topics are written three to a call, and the calls run at the same time
    plan_topics = plan['topics']
    groups = [list(range(i, min(i + 3, len(plan_topics)))) for i in range(0, len(plan_topics), 3)]

    def write_topics(k, idx):
        group, js = [plan_topics[i] for i in idx], list(dict.fromkeys(min(i, len(names) - 1) for i in idx))
        book_text = ctx['whole'] or '\n\n'.join(f"### {names[j]}\n{ctx['per_topic'][j]}" for j in js)
        out = job.ask(f'topics_{k}', fill(read('nongate/topic.md'), **base, MODULE=plan['title'], TOPICS=json.dumps(group, ensure_ascii=False),
                                          OTHERS=', '.join(t['title'] for t in plan_topics if t not in group) or '(none)',
                                          BOOK_NOTE=book_note(any(ctx['found'][j] for j in js)), BOOK=book_text),
                      tidy=C.nongate_topics, problems=lambda out: C.nongate_topics_problems(out, len(group)))
        return [{'title': g['title'], 'tagline': g.get('tagline', ''), 'blocks': t['blocks']} for g, t in zip(group, out['topics'])]

    job.progress(f'Writing {len(plan_topics)} topics (at the same time)')
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        topics = [t for part in pool.map(write_topics, range(len(groups)), groups) for t in part]

    job.progress('Writing case study, practice and revision sheet')
    summary = '\n'.join(f"{k}. {t['title']}: {t.get('tagline', '')}" for k, t in enumerate(topics, 1))
    end = job.ask('end', fill(read('nongate/end.md'), **base, MODULE=plan['title'], TOPICS=summary, N_PRACTICE=plan.get('n_practice', 10)),
                  tidy=C.nongate_end, problems=C.nongate_end_problems)

    content = job.step('content', lambda: {
        'title': plan['title'], 'description': plan.get('description', ''), 'subject': o['subject'], 'study_time': plan.get('study_time', ''),
        'audience': plan.get('audience', ''), 'topics': topics, 'case_study': end.get('case_study') if plan.get('case_study', True) else None,
        'practice': end['practice'], 'revision': end.get('revision')})
    job.progress('Rendering the PDF')
    render_and_store(job, 'nongate', content)


def process(rt, run):
    """Run one topic through its pipeline. Raises CapReached or Cancelled; the worker handles those."""
    job = Job(rt, run)
    (gate if run['mode'] == 'gate' else nongate)(job)
    db.event(run['created_by'], 'pdf ready', run['id'], topic=rt['name'])


def rerender(rt, run, content):
    """Render an edited content JSON again (no model call): used when a user uploads a corrected JSON."""
    job = Job(rt, run)
    bad = [p for p, m, hard in C.drawing_problems(content) if hard]
    if bad: C.drop(content, bad); job.warn(f'{len(bad)} figure(s) in the uploaded JSON could not be drawn and were left out.')
    render_and_store(job, 'gate' if run['mode'] == 'gate' else 'nongate', content)

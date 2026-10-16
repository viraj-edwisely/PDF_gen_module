"""Generation pipeline: one run_topic -> content JSON -> PDF.

Every finished step is saved in the `steps` table, so an interrupted run resumes without paying again.
GATE: context -> PYQs -> plan -> notes -> practice -> sample paper -> wrap-up -> checks and repair -> PDF.
Non-GATE: context -> plan -> one call per topic -> end matter -> checks -> PDF.
"""
import json, os, re, subprocess, sys, tempfile
import db, llm, pyq, retrieve
from config import PROVIDERS

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, 'render')
sys.path.insert(0, RENDER)
from check_gate_level import check   # noqa: E402  (pure Python, no matplotlib)

GATE_BLOCKS = {'para', 'subhead', 'bullets', 'numbered', 'formula', 'table', 'example', 'trap', 'note', 'callout', 'code', 'figure', 'image', 'spacer', 'pagebreak'}
NONGATE_BLOCKS = {'situation', 'concept', 'worked_example', 'pitfall', 'note', 'quick_check', 'para', 'table', 'bullets', 'numbered', 'formula', 'figure', 'subhead'}
# checker messages -> the part of the content a repair call rewrites
REPAIR_GROUPS = {'questions': (r'^(P\d+|S\d+|practice|sample paper)', ['practice', 'sample_paper'], '{"practice": [...], "sample_paper": {...}}'),
                 'notes': (r'^(notes|only \d+ concept|\d+ worked|no figures|internal ID)', ['notes'], '{"notes": [...]}'),
                 'wrap': (r'^(missing "traps"|revision)', ['traps', 'revision_card'], '{"traps": [...], "revision_card": [...]}')}


NUMERIC_NOTE = 'Numeric answers are not independently verified: check the answer key before publishing.'


class CapReached(Exception): pass
class Cancelled(Exception): pass


def read(path):
    return open(os.path.join(HERE, 'prompts', path), encoding='utf-8').read()


def fill(template, **values):
    """Replace {{NAME}} in one pass, so text inside a value (book text) is never treated as a placeholder."""
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(values.get(m.group(1), m.group(0))), template)


def system_prompt(mode):
    if mode == 'gate':
        return fill(read('gate/system.md'), STANDARD=read('gate/gate_level_standard.md'), SCHEMA=read('gate/content_schema.md'), FIGURES=read('figure_catalogue.md'))
    example = open(os.path.join(RENDER, 'example_nongate.json'), encoding='utf-8').read()
    return fill(read('nongate/system.md'), SCHEMA=read('nongate/content_schema.md'), FIGURES=read('figure_catalogue.md'), EXAMPLE=example)


class Job:
    """One run_topic being processed: saved steps, model calls with validation, warnings, progress, cost cap."""

    def __init__(self, rt, run):
        self.rt, self.run, self.provider = rt, run, run['provider']
        self.system = system_prompt(run['mode'])
        self.feedback = (run['options'] or {}).get('feedback')

    def _guard(self):
        status = db.sql('select status from runs where id=%s', (self.run['id'],))[0]['status']
        if status == 'cancelled': raise Cancelled()

    def progress(self, text):
        db.sql('update run_topics set step=%s where id=%s', (text, self.rt['id']))
        db.sql('update runs set heartbeat_at=now() where id=%s', (self.run['id'],))

    def warn(self, text):
        db.sql('update run_topics set warnings = warnings || to_jsonb(%s::text) where id=%s', (text, self.rt['id']))

    def saved(self, name):
        rows = db.sql('select output from steps where run_topic_id=%s and name=%s', (self.rt['id'], name))
        return rows[0]['output'] if rows else None

    def save(self, name, output, usage):
        db.sql('insert into steps (run_topic_id, name, output, input_tokens, output_tokens, cost_usd) values (%s,%s,%s::jsonb,%s,%s,%s) '
               'on conflict (run_topic_id, name) do update set output=excluded.output, input_tokens=excluded.input_tokens, '
               'output_tokens=excluded.output_tokens, cost_usd=excluded.cost_usd', (self.rt['id'], name, json.dumps(output), usage['in'], usage['out'], usage['cost']))
        db.sql('update run_topics set cost_usd = cost_usd + %s where id=%s', (usage['cost'], self.rt['id']))
        run = db.sql('update runs set cost_usd = cost_usd + %s, heartbeat_at=now() where id=%s returning cost_usd, cost_cap', (usage['cost'], self.run['id']))[0]
        if run['cost_usd'] >= run['cost_cap']: raise CapReached()

    def step(self, name, fn):
        """A step that makes no model call itself (it may call ask() inside). Runs once; the output is saved."""
        self._guard()
        out = self.saved(name)
        if out is None:
            out = fn()
            self.save(name, out, {'in': 0, 'out': 0, 'cost': 0})
        return out

    def ask(self, name, user, validate=None):
        """One model call as a saved step. If validate(output) lists problems, the model is asked again (twice at most)."""
        self._guard()
        out = self.saved(name)
        if out is not None: return out
        if self.feedback: user += f'\n\nExtra instructions from the user for this PDF: {self.feedback}'
        total, problems, out = {'in': 0, 'out': 0, 'cost': 0.0}, [], None
        for _ in range(3):
            ask = user if not problems else user + '\n\nYour previous reply had these problems. Fix them and return the full JSON again:\n- ' + '\n- '.join(problems)
            try:
                out, usage = llm.generate_json(self.provider, self.system, ask)
            except llm.LLMError as e:
                problems, out = [str(e)], None; continue
            for k in total: total[k] += usage[k]
            problems = validate(out) if validate else []
            if not problems: break
        if out is None: raise llm.LLMError('; '.join(problems))
        if problems: self.warn(f'{name}: problems the model did not fix: ' + '; '.join(problems[:4]))
        self.save(name, out, total)
        return out


# ---------------------------------------------------------------- validators (structure only; the GATE checker does the rest)
def block_errors(blocks, allowed, where):
    if not isinstance(blocks, list) or not blocks: return [f'{where}: blocks must be a non-empty list']
    errs = []
    for i, b in enumerate(blocks):
        if isinstance(b, str): continue
        t = b.get('type', 'para') if isinstance(b, dict) else None
        if t not in allowed: errs.append(f'{where} block {i}: unknown type {t!r}')
        elif t == 'table' and not (b.get('header') and b.get('rows')): errs.append(f'{where} block {i}: table needs header and rows')
        elif t == 'figure' and not (b.get('kind') and isinstance(b.get('spec'), dict)): errs.append(f'{where} block {i}: figure needs kind and spec')
        elif t in ('example', 'worked_example') and not (b.get('problem') or b.get('text')): errs.append(f'{where} block {i}: example has no content')
        elif t == 'quick_check' and not all(isinstance(x, dict) and x.get('q') and x.get('a') for x in b.get('items') or [{}]): errs.append(f'{where} block {i}: quick_check items need q and a')
    return errs


def notes_errors(expected):
    def check_notes(out):
        notes = out.get('notes') if isinstance(out, dict) else None
        if not isinstance(notes, list) or len(notes) != len(expected): return [f'"notes" must be a list of {len(expected)} sections']
        return [e for n in notes for e in block_errors(n.get('blocks'), GATE_BLOCKS, n.get('heading', '?'))]
    return check_notes


def question_errors(paper, practice=None, sample=None, prior_practice=None):
    """Run the GATE checker on the practice questions or on the sample paper alone and keep the messages about that part."""
    stub = {'paper': paper, 'practice': practice or prior_practice or [], 'sample_paper': sample or {}}
    return [e for e in check(stub)[0] if re.match(r'^(P\d+|practice)' if practice else r'^(S\d+|sample paper)', e)]


# ---------------------------------------------------------------- shared steps
def book_note(found):
    return 'Book material for this topic follows.' if found else 'The book has NO material on this topic in the chosen scope: write it from your own knowledge.'


def figure_failures(content):
    """Draw every figure in a subprocess; drop the ones that fail. Returns a list of warnings."""
    path = os.path.join(tempfile.mkdtemp(), 'content.json')
    json.dump(content, open(path, 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, os.path.join(RENDER, 'check_figures.py'), path], capture_output=True, text=True, timeout=300)
    if r.returncode: return ['figures could not be checked: ' + r.stderr[-150:]]
    warnings = []
    for f in sorted(json.loads(r.stdout), key=lambda f: f['path'], reverse=True):     # deepest/last first so list indexes stay valid
        parent = content
        for key in f['path'][:-1]: parent = parent[key]
        if isinstance(parent, list): del parent[f['path'][-1]]
        else: parent.pop(f['path'][-1], None)
        warnings.append('a figure was dropped because it could not be drawn: ' + f['error'][:100])
    return warnings


def render_and_store(job, mode, content):
    """Render the PDF in a subprocess, upload PDF and JSON, mark the topic finished."""
    folder = tempfile.mkdtemp(); src, pdf = os.path.join(folder, 'content.json'), os.path.join(folder, 'out.pdf')
    json.dump(content, open(src, 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, os.path.join(RENDER, f'render_{mode}.py'), src, pdf], capture_output=True, text=True, timeout=600)
    if r.returncode: raise RuntimeError('PDF rendering failed: ' + r.stderr[-300:])
    base = f"{job.run['id']}/{job.rt['id']}"
    db.upload('outputs', base + '.pdf', open(pdf, 'rb').read(), 'application/pdf')
    db.upload('outputs', base + '.json', json.dumps(content, ensure_ascii=False).encode('utf-8'), 'application/json')
    warns = db.sql('select warnings from run_topics where id=%s', (job.rt['id'],))[0]['warnings']
    if mode == 'gate' and NUMERIC_NOTE not in warns: job.warn(NUMERIC_NOTE); warns.append(NUMERIC_NOTE)
    db.sql("update run_topics set status=%s, step='done', pdf_path=%s, json_path=%s where id=%s", ('warnings' if warns else 'done', base + '.pdf', base + '.json', job.rt['id']))


# ---------------------------------------------------------------- GATE
def pyq_step(job, topic, o):
    """Previous-year questions from the user's URLs and optional workbook; only those found verbatim in the source are kept."""
    texts, extra = [], []
    for url in o.get('urls') or []:
        try: texts.append(pyq.fetch_text(url))
        except Exception as e: job.warn(f'PYQ source could not be read ({url}): {e}')
    workbook = (o.get('workbook') or {}).get(topic)
    if workbook:
        texts.append('\n\n'.join(f"[{q['source']}] [{q['qtype']}, {q['marks']} mark(s)]\n{q['question']}\n" + ''.join(f'({"ABCD"[i]}) {x}\n' for i, x in enumerate(q.get('options') or [])) + f"Answer: {q['answer']}" for q in workbook))
    if not texts:
        job.warn('No previous-year questions: no readable source was given. The PYQ section is left out.'); return []
    found = []
    for i, text in enumerate(texts):
        out = job.ask(f'pyq_{i}', fill(read('gate/pyq_extract.md'), TOPIC=topic, PAPER=o['paper'], SUBJECT=o['subject'], SOURCE=text[:120_000]))
        found += out.get('questions') or []
    kept, dropped = pyq.keep_verified(found, texts)
    unique = {re.sub(r'\W+', '', q['question'].lower())[:80]: q for q in kept}
    kept = list(unique.values())[:8]
    if not kept: job.warn('No previous-year questions on this topic were found in the given sources. The PYQ section is left out.')
    for d in dropped[:3]: job.warn('A question was ignored: ' + d)
    return kept


def repair(job, content, errors, rnd):
    """Send each group of checker errors back to the model with the part it must rewrite."""
    rest = list(errors)
    for i in sorted({int(m.group(1)) for e in errors if (m := re.match(r'PYQ(\d+)', e))}, reverse=True):   # official questions are dropped, never rewritten
        del content['pyqs'][i - 1]; job.warn(f'Previous-year question {i} was removed because it did not pass the checks.')
    rest = [e for e in rest if not e.startswith('PYQ')]
    for group, (pattern, keys, form) in REPAIR_GROUPS.items():
        errs = [e for e in rest if re.match(pattern, e)] or ([e for e in rest if not any(re.match(p, e) for p, _, _ in REPAIR_GROUPS.values())] if group == 'notes' else [])
        if not errs: continue
        out = job.ask(f'repair{rnd}_{group}', fill(read('gate/repair.md'), PART=group, TOPIC=job.rt['name'], ERRORS='\n'.join('- ' + e for e in errs),
                                                   CURRENT=json.dumps({k: content[k] for k in keys}, ensure_ascii=False), FORMAT=form))
        content.update({k: out[k] for k in keys if k in out})


def gate(job):
    run, rt = job.run, job.rt
    o, topic = run['options'], rt['name']
    book = db.sql('select * from books where id=%s', (run['book_id'],))[0]
    job.progress('Reading the book')
    def context():
        ctx = retrieve.topic_context(book, run['scope_start'], run['scope_end'], topic)
        if not ctx['found']: job.warn('Topic not found in the chosen book scope: written from the model\'s own knowledge, not grounded in the book.')
        return ctx
    ctx = job.step('context', context)
    book_text, note = (ctx['text'] if ctx['found'] else ''), book_note(ctx['found'])
    job.progress('Previous-year questions')
    pyqs = job.step('pyq', lambda: pyq_step(job, topic, o))
    pyq_brief = '\n'.join('- ' + q['question'][:160] for q in pyqs) or '(none)'
    base = dict(TOPIC=topic, PAPER=o['paper'], SUBJECT=o['subject'], BOOK=book_text, BOOK_NOTE=note)

    job.progress('Planning the sections')
    def plan_errors(p):
        s = p.get('sections') if isinstance(p, dict) else None
        return [] if isinstance(s, list) and 3 <= len(s) <= 12 and all(x.get('heading') for x in s) and p.get('objectives') else ['need 3 to 12 sections with headings, and objectives']
    plan = job.ask('plan', fill(read('gate/plan.md'), **base, PYQS=pyq_brief, SYLLABUS=o.get('syllabus_line') or ''), plan_errors)
    archetypes = '; '.join(plan.get('archetypes') or [])

    notes, sections = [], plan['sections']
    for i in range(0, len(sections), 2):
        group = sections[i:i + 2]
        job.progress(f'Writing notes {min(i + 2, len(sections))} of {len(sections)}')
        out = job.ask(f'notes_{i}', fill(read('gate/notes.md'), **base, SECTIONS=json.dumps(group, ensure_ascii=False), DONE=', '.join(n['heading'] for n in notes) or '(none)', ARCHETYPES=archetypes),
                      notes_errors(group))
        notes += out['notes']
    headings = ', '.join(n['heading'] for n in notes)

    job.progress('Writing practice questions')
    practice = job.ask('practice', fill(read('gate/practice.md'), **base, ARCHETYPES=archetypes, HEADINGS=headings, PYQS=pyq_brief),
                       lambda out: question_errors(o['paper'], practice=out.get('practice')) if isinstance(out.get('practice'), list) else ['"practice" must be a list'])['practice']
    job.progress('Writing the sample paper')
    stems = '\n'.join('- ' + q['question'][:140] for q in practice)
    sample = job.ask('sample', fill(read('gate/sample.md'), **base, ARCHETYPES=archetypes, PRACTICE_STEMS=stems),
                     lambda out: question_errors(o['paper'], sample=out.get('sample_paper'), prior_practice=practice) if isinstance(out.get('sample_paper'), dict) else ['"sample_paper" must be an object'])['sample_paper']
    job.progress('Writing traps and revision card')
    wrap = job.ask('wrapup', fill(read('gate/wrapup.md'), **base, HEADINGS=headings, ARCHETYPES=archetypes),
                   lambda out: [] if out.get('traps') and out.get('revision_card') else ['need "traps" and "revision_card"'])

    def assemble():
        c = {'paper': o['paper'], 'subject': o['subject'], 'topic_name': topic, 'syllabus_line': plan.get('syllabus_line', ''), 'subtitle': plan.get('subtitle', ''),
             'objectives': plan['objectives'], 'prerequisites': plan.get('prerequisites', []), 'notes': notes, 'traps': wrap['traps'], 'revision_card': wrap['revision_card'],
             'pyqs': pyqs, 'practice': practice, 'sample_paper': sample}
        for rnd in (1, 2):
            errors = check(c)[0]
            if not errors: break
            job.progress(f'Fixing checker problems (round {rnd})'); repair(job, c, errors, rnd)
        errors = check(c)[0]
        if errors: job.warn('Problems left after repair: ' + '; '.join(errors[:5]) + (f' (+{len(errors) - 5} more)' if len(errors) > 5 else ''))
        for w in figure_failures(c): job.warn(w)
        return c
    job.progress('Checking and assembling')
    content = job.step('content', assemble)
    job.progress('Rendering the PDF')
    render_and_store(job, 'gate', content)


# ---------------------------------------------------------------- Non-GATE
def nongate(job):
    run, rt = job.run, job.rt
    o, names = run['options'], run['options']['topics']
    book = db.sql('select * from books where id=%s', (run['book_id'],))[0]
    user_prompt = o.get('prompt') or ''
    job.progress('Reading the book')
    def context():
        ctxs = [retrieve.topic_context(book, run['scope_start'], run['scope_end'], t) for t in names]
        for t, c in zip(names, ctxs):
            if not c['found']: job.warn(f'Topic "{t}" not found in the chosen book scope: written from the model\'s own knowledge, not grounded in the book.')
        whole = ctxs[0]['text'] if all(c['whole_scope'] for c in ctxs) else None
        return {'whole': whole, 'per_topic': [c['text'] if c['found'] else '' for c in ctxs], 'found': [c['found'] for c in ctxs]}
    ctx = job.step('context', context)
    any_found = any(ctx['found'])
    base = dict(SUBJECT=o['subject'], USER_PROMPT=user_prompt or '(none: use the standard template)')

    job.progress('Planning the module')
    def plan_errors(p):
        return [] if isinstance(p, dict) and p.get('title') and isinstance(p.get('topics'), list) and p['topics'] and all(t.get('title') for t in p['topics']) else ['need "title" and a non-empty "topics" list with titles']
    plan = job.ask('plan', fill(read('nongate/plan.md'), **base, TOPICS='; '.join(names), STUDY_TIME=o.get('study_time') or '', AUDIENCE=o.get('audience') or '',
                                BOOK_NOTE=book_note(any_found), BOOK=ctx['whole'] or '\n\n'.join(ctx['per_topic'])[:160_000]), plan_errors)

    topics = []
    for i, t in enumerate(plan['topics']):
        job.progress(f"Writing topic {i + 1} of {len(plan['topics'])}")
        j = min(i, len(names) - 1)
        out = job.ask(f'topic_{i}', fill(read('nongate/topic.md'), **base, N=i + 1, MODULE=plan['title'], TITLE=t['title'], TAGLINE=t.get('tagline', ''), FOCUS=t.get('focus', ''),
                                         OTHERS=', '.join(x['title'] for x in plan['topics'] if x is not t), BOOK_NOTE=book_note(ctx['found'][j]), BOOK=ctx['whole'] or ctx['per_topic'][j]),
                      lambda out: block_errors(out.get('blocks'), NONGATE_BLOCKS, t['title']) if isinstance(out, dict) else ['reply must be an object with "blocks"'])
        topics.append({'title': t['title'], 'tagline': t.get('tagline', ''), 'blocks': out['blocks']})

    job.progress('Writing case study, practice and revision sheet')
    summary = '\n'.join(f"{k}. {t['title']}: {t.get('tagline', '')}" for k, t in enumerate(topics, 1))
    def end_errors(out):
        p = out.get('practice') if isinstance(out, dict) else None
        return [] if isinstance(p, list) and p and all(isinstance(x, dict) and x.get('question') and x.get('answer') for x in p) else ['"practice" must be a list of {tag, question, answer}']
    end = job.ask('end', fill(read('nongate/end.md'), **base, MODULE=plan['title'], TOPICS=summary, N_PRACTICE=plan.get('n_practice', 10)), end_errors)

    def assemble():
        c = {'title': plan['title'], 'description': plan.get('description', ''), 'subject': o['subject'], 'study_time': plan.get('study_time', ''), 'audience': plan.get('audience', ''),
             'topics': topics, 'case_study': end.get('case_study') if plan.get('case_study', True) else None, 'practice': end['practice'], 'revision': end.get('revision')}
        for w in figure_failures(c): job.warn(w)
        return c
    job.progress('Checking and assembling')
    content = job.step('content', assemble)
    job.progress('Rendering the PDF')
    render_and_store(job, 'nongate', content)


def process(rt, run):
    """Run one topic through its pipeline. Raises CapReached or Cancelled; the worker handles those."""
    job = Job(rt, run)
    (gate if run['mode'] == 'gate' else nongate)(job)


def rerender(rt, run, content):
    """Render an edited content JSON again (no model call): used when a user uploads a corrected JSON."""
    job = Job(rt, run)
    mode = 'gate' if run['mode'] == 'gate' else 'nongate'
    for w in figure_failures(content): job.warn(w)
    render_and_store(job, mode, content)

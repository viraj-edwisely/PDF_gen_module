"""Checks that need eyes: the model looks at each figure and each page of a GATE PDF (optional, per run), and the
illustration library (pictures of machines and apparatus, generated once per concept and approved by a person).

- figures(): every figure as an image with what it should show; a figure found wrong goes back to the writer once.
- pages():   the finished pages; what looks wrong becomes a note on the Runs page.
- illustrations(): "illustration" figures take their picture from the library; a concept with no approved picture is
  left out, and (when the run allows it) drawn once, checked by the model and queued for approval.
"""
import json, os, re, subprocess, sys, tempfile
import content as C, db, llm
from config import ILLUSTRATIONS_PER_RUN

RENDER = C.RENDER
BATCH_FIGURES, BATCH_PAGES = 6, 8


def _read(name):
    return open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts', name), encoding='utf-8').read()


def _fill(t, **v):
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(v.get(m.group(1), m.group(0))), t)


def figure_pngs(content):
    """[(path, png bytes, info)] for every figure that draws (drawn in a subprocess, like the renderer)."""
    d = tempfile.mkdtemp()
    src = os.path.join(d, 'content.json'); json.dump(content, open(src, 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, os.path.join(RENDER, 'figure_pngs.py'), src, os.path.join(d, 'png')], capture_output=True, text=True, encoding='utf-8', timeout=900)
    if r.returncode: return []
    return [(tuple(f['path']), open(f['file'], 'rb').read(), f) for f in json.loads(r.stdout.strip().splitlines()[-1])]


def figures(job, topic, o, content, plan):
    """The model looks at every figure with what it should show; the items holding wrong figures are repaired once."""
    purposes = {s['heading']: s.get('figure', '') for s in plan.get('sections', [])}
    found = figure_pngs(content)
    if not found: return content
    issues = []
    for b in range(0, len(found), BATCH_FIGURES):
        part = found[b:b + BATCH_FIGURES]
        items = []
        for path, _, f in part:
            sec = content['notes'][path[1]]['heading'] if path[:1] == ('notes',) and len(path) > 1 and path[1] < len(content['notes']) else ''
            items.append({'ref': C.ref(path), 'section': sec, 'should_show': purposes.get(sec, ''), 'kind': f['kind'], 'title': f['title'], 'caption': f['caption']})
        refs = {i['ref'] for i in items}
        tidy = lambda x: {'issues': [i for i in C._list(x.get('issues') if isinstance(x, dict) else None) if isinstance(i, dict) and i.get('ref') in refs]}
        try: out = job.ask(f'visual_figures_{b // BATCH_FIGURES}', _fill(_read('gate/visual.md'), TOPIC=topic, PAPER=o['paper'], SUBJECT=o['subject'],
                                                                       ITEMS=json.dumps(items, ensure_ascii=False)), tidy=tidy, images=[png for _, png, _ in part])
        except llm.LLMError as e: job.warn(f'The visual review of the figures was skipped ({str(e)[:120]}).'); return content
        issues += out['issues']
    job.log(f'Visual review: {len(issues)} of {len(found)} figures need changes')
    if not issues: return content
    probs = [(C.item_path(C.unref(i['ref'])), f"a review of the drawn figure found: {str(i.get('problem', ''))[:300]}. Fix the figure's spec (or choose the "
              'right figure kind) so it shows this correctly', False) for i in issues]
    keep = {k: v for k, v in content.items() if k not in ('notes', 'practice', 'sample_paper')}
    levels = [q.get('level') for q in content.get('practice', [])]
    def tidy_fix(x):
        for q, lvl in zip(x.get('practice', []), levels): q['level'] = lvl
        q = C.gate_questions({**x, 'traps': content.get('traps'), 'revision_card': content.get('revision_card')})
        return {**keep, **C.gate_notes(x), 'practice': q['practice'], 'sample_paper': q['sample_paper']}
    fixed = job.revise('visual_fix', content, probs, tidy_fix, lambda x: C.drawing_problems({k: x[k] for k in ('notes', 'practice', 'sample_paper')}))
    for p, _, _ in probs:
        try: job.warn(f'{C.label(p, fixed)}: a figure was redrawn after the visual review. Please look at it.')
        except Exception: pass
    return fixed


def pages(job, topic, pdf):
    """The finished pages, looked at in batches; what looks wrong becomes a note (the PDF is already made)."""
    import pymupdf
    doc = pymupdf.open(stream=pdf, filetype='pdf')
    for b in range(1, doc.page_count, BATCH_PAGES):                     # the cover is skipped
        nums = list(range(b, min(b + BATCH_PAGES, doc.page_count)))
        imgs = [doc[i].get_pixmap(dpi=70).tobytes('png') for i in nums]
        tidy = lambda x: {'issues': [i for i in C._list(x.get('issues') if isinstance(x, dict) else None) if isinstance(i, dict) and i.get('problem')]}
        try: out = job.ask(f'visual_pages_{b}', _fill(_read('gate/visual_pages.md'), TOPIC=topic, PAGES=', '.join(str(i + 1) for i in nums)), tidy=tidy, images=imgs)
        except llm.LLMError as e: job.warn(f'The visual review of the pages was skipped ({str(e)[:120]}).'); return
        for i in out['issues'][:6]: job.warn(f"Page {i.get('page', '?')}: {str(i['problem'])[:200]} (visual review)")


def key(spec):
    return re.sub(r'[^a-z0-9]+', '_', str(spec.get('concept') or spec.get('title') or '').lower()).strip('_')[:60]


def prompt(spec):
    parts = [str(p) for p in spec.get('parts', [])]
    return ('Flat technical illustration for an engineering textbook: white background, clean vector line style, purple (#4D2A87) '
            f"and gold (#D9A400) accents, neutral greys. Subject: {spec.get('title') or spec.get('concept')}. {spec.get('description', '')} "
            f"Mark these parts with small numbered callouts 1 to {len(parts)}, in this order: " + '; '.join(f'{k + 1} {p}' for k, p in enumerate(parts)) +
            '. No words or letters anywhere, only the callout numbers. No watermark, no border.')


def check(job, spec, png, usage):
    """The model looks at a new illustration: None when it shows what it should, else the problem."""
    try:
        out, u, _ = llm.generate_json(job.system, _fill(_read('gate/illustration_check.md'), TITLE=spec.get('title') or spec.get('concept'),
                                                        DESCRIPTION=spec.get('description', ''), PARTS='; '.join(map(str, spec.get('parts', [])))), 4000, job.effort, [png])
        for k in usage: usage[k] += u.get(k, 0)
        return None if out.get('ok') else str(out.get('problem') or 'not as described')[:300]
    except llm.LLMError as e: return f'it could not be checked ({str(e)[:100]})'


def new_picture(job, spec, k):
    """Draw a concept once (and once more if the check finds a problem), store it and queue it for approval."""
    usage = {'in': 0, 'out': 0, 'cost': 0.0}
    text, problem, png = prompt(spec), None, None
    for attempt in range(2):
        png, price = llm.generate_image(text if not problem else text + f' Correct this: {problem}')
        usage['cost'] += price
        problem = check(job, spec, png, usage)
        if not problem: break
    path = f'{k}.png'
    db.upload('illustrations', path, png, 'image/png')
    db.sql("insert into illustrations (concept, title, description, parts, path, status, review, created_by) values (%s,%s,%s,%s::jsonb,%s,%s,%s,%s) "
           "on conflict (concept) do update set path=excluded.path, status=excluded.status, review=excluded.review",
           (k, spec.get('title'), spec.get('description'), json.dumps(spec.get('parts', [])), path, 'pending' if not problem else 'rejected',
            problem or 'The model found no problem.', job.run['created_by']))
    job.charge(usage, f'illustration {k}')
    return problem


def illustrations(job, content, allow_new):
    """Fill "illustration" figures from the library (a temp file per picture); leave out those not approved yet.
    Returns (content, temp folder to delete after rendering)."""
    found = [(p, f) for p, f in walk_figures(content) if f.get('kind') == 'illustration']
    if not found: return content, None
    folder, drop, made = tempfile.mkdtemp(), [], 0
    for path, f in found:
        spec, k = f.setdefault('spec', {}), key(f.get('spec') or {})
        row = db.sql('select * from illustrations where concept=%s', (k,)) if k else []
        if row and row[0]['status'] == 'approved':
            spec['file'] = os.path.join(folder, k + '.png')
            open(spec['file'], 'wb').write(db.download('illustrations', row[0]['path']))
            spec.setdefault('parts', row[0]['parts'] or [])
            continue
        drop.append(path)
        if not k: continue
        if not row and allow_new and made < ILLUSTRATIONS_PER_RUN:
            made += 1
            try: problem = new_picture(job, spec, k)
            except Exception as e: job.warn(f'The illustration "{k}" could not be drawn ({str(e)[:120]}).'); continue
            job.warn(f'New illustration "{k}" drawn and waiting for approval on the Illustrations page' + (f' (the check found: {problem})' if problem else '') +
                     '. This PDF leaves it out; regenerate after approval to include it.')
        else: job.warn(f'The illustration "{k}" is not approved yet ({row[0]["status"] if row else "not drawn"}), so this PDF leaves it out.')
    C.drop(content, drop)
    return content, folder


def walk_figures(x, path=()):
    """(path, figure) for every figure of a content JSON, in blocks and in questions."""
    if isinstance(x, dict):
        if 'kind' in x and ('spec' in x or x.get('type') == 'figure'): yield path, x
        for k, v in x.items():
            if k != 'spec': yield from walk_figures(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from walk_figures(v, path + (i,))

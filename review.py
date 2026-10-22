"""Checks that need eyes: the model looks at each figure and each page of a GATE PDF (optional, per run), and the
illustration library (pictures of machines and apparatus, generated once per concept and approved by a person).

- figures(): every figure as an image with what it should show; a figure found wrong goes back to the writer (twice at most,
  each time looked at again) and is left out if it is still wrong.
- drop_bad_figures(): figures whose labels still collide, or that are the wrong kind of figure, are left out.
- pages():   the finished pages; what looks wrong becomes a note on the Runs page.
- illustrations(): "illustration" figures take their picture from the library; a concept not in it is (when the run allows it)
  drawn once (one low-quality image call, no check, no redraw), numbered by the image model itself. A picture waiting for approval
  is used like an approved one (a note asks for its approval); a rejected one is left out.
"""
import io, json, os, re, subprocess, sys, tempfile
from PIL import Image
import content as C, db, llm
from config import ILLUSTRATIONS_PER_RUN

RENDER = C.RENDER
BATCH_FIGURES, BATCH_PAGES = 6, 8
ROUNDS = 2                           # repairs of the figures found wrong, each followed by another look
QUESTIONS = ('practice', 'sample_paper', 'pyqs')


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


def look(job, topic, o, content, purposes, rnd, only):
    """The model looks at the figures (only those in `only`, when given) with what each should show: its list of issues."""
    found = [f for f in figure_pngs(content) if only is None or C.ref(f[0]) in only]
    issues = []
    for b in range(0, len(found), BATCH_FIGURES):
        part = found[b:b + BATCH_FIGURES]
        items = []
        for path, _, f in part:
            sec = content['notes'][path[1]]['heading'] if path[:1] == ('notes',) and len(path) > 1 and path[1] < len(content['notes']) else ''
            items.append({'ref': C.ref(path), 'section': sec, 'should_show': purposes.get(sec, ''), 'kind': f['kind'], 'title': f['title'], 'caption': f['caption']})
        refs = {i['ref'] for i in items}
        tidy = lambda x: {'issues': [i for i in C._list(x.get('issues') if isinstance(x, dict) else None) if isinstance(i, dict) and i.get('ref') in refs]}
        try: out = job.ask(f'visual_figures_{rnd}_{b // BATCH_FIGURES}', _fill(_read('gate/visual.md'), TOPIC=topic, PAPER=o['paper'], SUBJECT=o['subject'],
                                                                             ITEMS=json.dumps(items, ensure_ascii=False)), tidy=tidy, images=[png for _, png, _ in part])
        except llm.LLMError as e: job.warn(f'The visual review of the figures was skipped ({str(e)[:120]}).'); return []
        issues += out['issues']
    job.log(f'Visual review, look {rnd + 1}: {len(issues)} of {len(found)} figures need changes')
    return issues


def repair(job, content, issues, rnd):
    """The items holding the figures found wrong go back to the writer; returns the content with the repaired items."""
    probs = [(C.item_path(C.unref(i['ref'])), f"a review of the drawn figure found: {str(i.get('problem', ''))[:300]}. Fix the figure's spec (or choose the "
              'right figure kind) so it shows this correctly', False) for i in issues]
    keep = {k: v for k, v in content.items() if k not in ('notes', 'practice', 'sample_paper')}
    levels = [q.get('level') for q in content.get('practice', [])]
    def tidy_fix(x):
        for q, lvl in zip(x.get('practice', []), levels): q['level'] = lvl
        q = C.gate_questions({**x, 'traps': content.get('traps'), 'revision_card': content.get('revision_card')})
        return {**keep, **C.gate_notes(x), 'practice': q['practice'], 'sample_paper': q['sample_paper']}
    return job.revise(f'visual_fix{rnd}', content, probs, tidy_fix, lambda x: C.drawing_problems({k: x[k] for k in ('notes', 'practice', 'sample_paper')}))


def leave_out(job, content, bad):
    """bad: [(figure path, problem)] of figures still wrong after their repairs. Such a figure is left out of the PDF, with a note.
    A question's figure stays (the question needs it, and dropping a question changes the marks): it is only noted."""
    gone = []
    for path, why in bad:
        where = C.label(C.item_path(path), content)
        if path[0] in QUESTIONS: job.warn(f'{where}: its figure is still not right ({why[:150]}). Please check it.')
        else: gone.append(path); job.warn(f'{where}: a figure was left out because it was still wrong after repairs ({why[:150]}).')
    C.drop(content, gone)


def drop_bad_figures(job, content):
    """Figures that draw but are muddled (labels still overlapping, the wrong kind of figure) after the writer's repair are left out."""
    leave_out(job, content, C.layout_problems(content))
    return content


def figures(job, topic, o, content, plan):
    """The model looks at every figure with what it should show; figures found wrong go back to the writer and are looked at
    again, up to ROUNDS times. What is still wrong after the last repair is left out."""
    purposes = {s['heading']: s.get('figure', '') for s in plan.get('sections', [])}
    only, redrawn = None, set()
    for rnd in range(ROUNDS + 1):
        issues = look(job, topic, o, content, purposes, rnd, only)
        if not issues: return content
        if rnd == ROUNDS: break
        content, only = repair(job, content, issues, rnd), {i['ref'] for i in issues}
        for i in issues:
            p = C.item_path(C.unref(i['ref']))
            if p not in redrawn: redrawn.add(p); job.warn(f'{C.label(p, content)}: a figure was redrawn after the visual review. Please look at it.')
    leave_out(job, content, [(C.unref(i['ref']), str(i.get('problem', ''))) for i in issues])
    return content


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


def brief(allow_new):
    """What the writer is told about illustrations: the pictures already in the library (approved, or drawn and waiting for approval:
    both appear in PDFs), and whether it may ask for a new one."""
    rows = db.sql("select concept, title, parts from illustrations where status in ('approved', 'pending') order by concept limit 60")
    have = '\n'.join(f"- {r['concept']} ({r['title']}): " + '; '.join(f'{k}. {p}' for k, p in enumerate(r['parts'] or [], 1)) for r in rows)
    new = (f'You may ask for at most {ILLUSTRATIONS_PER_RUN} NEW pictures, only of real apparatus or a cut-away that a student must recognise and that no computed or drawn '
           'kind can show: a snake_case "concept", a "title", a "description" of the view (what is cut away, what state it is in) and 4 to 8 named "parts". '
           'It is drawn once and reused by every later PDF.') if allow_new else 'New pictures are not allowed for this PDF: use only the listed pictures, or another kind.'
    return ('Pictures in the illustration library (kind "illustration": use its exact "concept" and name its parts as listed):\n' + (have or '(none yet)') + '\n' + new)


def prompt(spec):
    parts = [str(p) for p in spec.get('parts', [])]
    return ('Flat technical illustration for an engineering textbook: white background, clean vector line style, purple (#4D2A87) '
            f"and gold (#D9A400) accents, neutral greys. Subject: {spec.get('title') or spec.get('concept')}. {spec.get('description', '')} "
            'Show these parts clearly and separately, each marked with its number in a small circle joined to the part by a thin leader line, '
            'numbered in this order: ' + '; '.join(f'{k}. {p}' for k, p in enumerate(parts, 1)) +
            '. The numbers are the only text: no names, titles or captions. No watermark, no border.')


def new_picture(job, spec, k):
    """Draw a concept once and store it as pending (PDFs use it at once; a person approves or rejects it on the Illustrations page).
    Stored at most 1024 pixels wide: a figure on a page needs no more."""
    png, price = llm.generate_image(prompt(spec))
    im = Image.open(io.BytesIO(png)); im.thumbnail((1024, 1024))
    out = io.BytesIO(); im.convert('RGB').save(out, 'PNG', optimize=True); png = out.getvalue()
    path = f'{k}.png'
    db.upload('illustrations', path, png, 'image/png')
    db.sql("insert into illustrations (concept, title, description, parts, path, status, review, created_by) values (%s,%s,%s,%s::jsonb,%s,'pending','',%s) "
           "on conflict (concept) do update set path=excluded.path, parts=excluded.parts, status='pending', review=''",
           (k, spec.get('title'), spec.get('description'), json.dumps(spec.get('parts', [])), path, job.run['created_by']))
    job.charge({'in': 0, 'out': 0, 'cost': price}, f'illustration {k}')


def illustrations(job, content, allow_new):
    """Fill "illustration" figures from the library (a temp file per picture). An approved picture is used as it is; one still waiting for
    approval is used too; a rejected one is left out. A concept not in the library is drawn now when the run
    allows it. Returns (content, temp folder to delete after rendering)."""
    found = [(p, f) for p, f in walk_figures(content) if f.get('kind') == 'illustration']
    if not found: return content, None
    folder, drop, made = tempfile.mkdtemp(), [], 0
    for path, f in found:
        spec, k = f.setdefault('spec', {}), key(f.get('spec') or {})
        row = db.sql('select * from illustrations where concept=%s', (k,)) if k else []
        if k and not row and allow_new and made < ILLUSTRATIONS_PER_RUN:
            made += 1
            try: new_picture(job, spec, k)
            except Exception as e: job.warn(f'The illustration "{k}" could not be drawn ({str(e)[:120]}).'); drop.append(path); continue
            row = db.sql('select * from illustrations where concept=%s', (k,))
            job.warn(f'New illustration "{k}" drawn and waiting for approval on the Illustrations page.')
        r = row[0] if row else None
        if r and r['status'] in ('approved', 'pending'):
            spec['file'] = os.path.join(folder, k + '.png')
            open(spec['file'], 'wb').write(db.download('illustrations', r['path']))
            spec['parts'] = r['parts'] or []
            if r['status'] == 'pending': job.warn(f'Illustration "{k}" is waiting for approval on the Illustrations page.')
            continue
        drop.append(path)
        if k: job.warn(f'The illustration "{k}" ' + (f'was rejected ({r["review"] or "see the Illustrations page"})' if r else 'is not in the library and new pictures are off') + ', so this PDF leaves it out.')
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

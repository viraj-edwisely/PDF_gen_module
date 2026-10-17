"""Content rules shared by the pipeline: tidy a model reply, find its problems, and edit it by path.

A model reply goes through   tidy (fix predictable slips in code)  ->  problems (what is still wrong)  ->  the pipeline
sends only the broken items back to the model, and drops what stays broken.

A problem is (path, message, hard):
- path ()            the reply as a whole is unusable (wrong shape): the model is asked again from scratch;
- path ('notes', 2, 'blocks', 4) or ('practice', 6) ...   one item: only that item goes back for repair;
- hard=True          the item is broken and is dropped if the repair does not fix it;
- hard=False         a requirement (a missing worked example or figure, a wrong answer check): kept, with a warning.
"""
import difflib, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, 'render')
sys.path.insert(0, RENDER)
from check_gate_level import check as gate_check   # noqa: E402  (pure Python)
from safe_eval import safe_eval                     # noqa: E402  (numpy only)
from tex import normalize as tex_normalize      # noqa: E402  (pure Python)
from llm import loads                               # noqa: E402  (json.loads that keeps LaTeX backslashes)

GATE_BLOCKS = {'para', 'subhead', 'bullets', 'numbered', 'formula', 'table', 'example', 'trap', 'note', 'callout', 'code', 'figure', 'spacer', 'pagebreak'}
NONGATE_BLOCKS = {'situation', 'concept', 'worked_example', 'pitfall', 'note', 'quick_check', 'para', 'table', 'bullets', 'numbered', 'formula', 'figure', 'subhead'}
FIGURE_KINDS = {'gantt', 'timeline', 'plot', 'bars', 'graph', 'cells', 'beam', 'circuit'}
FIELD = {'para': 'text', 'subhead': 'text', 'bullets': 'items', 'numbered': 'items', 'formula': 'latex', 'code': 'text', 'callout': 'text',
         'trap': 'text', 'situation': 'text', 'concept': 'text', 'pitfall': 'text', 'worked_example': 'text', 'quick_check': 'items'}
ALIASES = {'text': ('content', 'body', 'value', 'paragraph', 'description', 'statement'), 'items': ('list', 'points', 'bullets', 'steps', 'entries', 'questions'),
           'latex': ('formula', 'expression', 'equation', 'tex', 'math', 'text'), 'header': ('headers', 'columns', 'head'), 'rows': ('data', 'body', 'cells'),
           'problem': ('question', 'statement', 'text', 'given'), 'solution': ('answer', 'working', 'steps', 'explanation')}
TYPE_ALIASES = {'paragraph': 'para', 'text': 'para', 'heading': 'subhead', 'subheading': 'subhead', 'list': 'bullets', 'bullet': 'bullets',
                'bullet_list': 'bullets', 'unordered_list': 'bullets', 'ordered_list': 'numbered', 'steps': 'numbered', 'equation': 'formula',
                'math': 'formula', 'diagram': 'figure', 'chart': 'figure', 'warning': 'trap', 'tip': 'note', 'box': 'note', 'important': 'callout',
                'key_point': 'callout', 'definition': 'note', 'worked-example': 'worked_example', 'workedexample': 'worked_example'}
BAD_TEX = re.compile(r'\\begin\{|\\end\{')          # left over after render/tex.py has rewritten a formula: cannot be drawn
CONTAINERS = ('blocks', 'practice', 'questions', 'traps', 'revision_card', 'paragraphs', 'concepts', 'mistakes', 'checklist', 'topics', 'notes')
LEVELS = ('Easy', 'Medium', 'Hard')


# ---------------------------------------------------------------- paths
def get(obj, path):
    for k in path: obj = obj[k]
    return obj


def put(obj, path, value):
    """Set the value at path; a missing last key or the list end appends."""
    parent, last = get(obj, path[:-1]), path[-1]
    if isinstance(parent, list) and last >= len(parent): parent.append(value)
    else: parent[last] = value


def drop(obj, paths):
    """Remove the items at these paths (later list indexes first, so earlier ones stay valid)."""
    for path in sorted(set(map(tuple, paths)), key=lambda p: [(-x if isinstance(x, int) else 0) for x in p]):
        try:
            parent = get(obj, path[:-1])
            if isinstance(parent, list): del parent[path[-1]]
            else: parent.pop(path[-1], None)
        except (KeyError, IndexError, TypeError): pass


def item_path(path):
    """The repairable item that contains `path`: ['notes', 0, 'blocks', 3, 'problem', 1] -> ('notes', 0, 'blocks', 3)."""
    path = list(path)
    for i in range(len(path) - 1):
        if path[i] in CONTAINERS and isinstance(path[i + 1], int) and path[i] not in ('notes', 'topics'):
            return tuple(path[:i + 2])
    return tuple(path[:2]) if path[0] in ('notes', 'topics') and len(path) > 1 else tuple(path[:1])


def label(path, obj=None):
    """A path in words for warnings: ('practice', 3) -> 'Practice Q4'; a notes path names its section heading."""
    p = list(path)
    if not p: return 'The reply'
    if p[0] == 'practice' and len(p) > 1: return f'Practice Q{p[1] + 1}'
    if p[:2] == ['sample_paper', 'questions'] and len(p) > 2: return f'Sample paper Q{p[2] + 1}'
    if p[0] in ('notes', 'topics') and len(p) > 1:
        try: name = f'"{get(obj, p[:2]).get("heading") or get(obj, p[:2]).get("title")}"'
        except (KeyError, IndexError, TypeError, AttributeError): name = str(p[1] + 1)
        return f"{'Section' if p[0] == 'notes' else 'Topic'} {name}" + (f', block {p[3] + 1}' if len(p) > 3 else '')
    names = {'traps': 'Common traps', 'revision_card': 'Revision card', 'case_study': 'Case study', 'revision': 'Revision sheet'}
    return names.get(p[0], str(p[0])) + (f' item {p[1] + 1}' if len(p) > 1 and isinstance(p[1], int) else '')


def ref(path): return '/'.join(map(str, path))
def unref(s): return tuple(int(x) if x.isdigit() else x for x in str(s).strip('/').split('/'))


# ---------------------------------------------------------------- tidy: fix predictable slips in code
def clean(x):
    """NUL characters out (the database refuses them); 'GATE 2027'-style target years out of printed text; escapes such as
    \\u0024 or \\u00bd that a model wrote out as text (double-escaped) back to their characters."""
    if isinstance(x, str):
        x = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), x.replace('\x00', ''))
        return re.sub(r'\bGATE\s*20\d\d\b', 'GATE', x.replace('\x00', ''))
    if isinstance(x, list): return [clean(v) for v in x]
    if isinstance(x, dict): return {k: clean(v) if k != 'source' else v for k, v in x.items()}
    return x


def _alias(d, field):
    if d.get(field) in (None, '', []):
        for a in ALIASES.get(field, ()):
            if d.get(a) not in (None, '', []): d[field] = d.pop(a); break
    return d


def _text(x):
    """A string from whatever the model put there (a list of lines, a dict with text)."""
    if isinstance(x, list): return '\n\n'.join(_text(v) for v in x)
    if isinstance(x, dict): return _text(x.get('text') or x.get('content') or ' '.join(str(v) for v in x.values()))
    return '' if x is None else str(x)


def block(b, mode):
    """One content block, tidied. Returns None for blocks that cannot be shown (images: the app draws all figures itself)."""
    if isinstance(b, str) and b.strip().startswith('{'):          # a block the model wrote as a string of JSON
        try: b = loads(b)
        except ValueError: pass
    if isinstance(b, str): return {'type': 'para', 'text': b}
    if not isinstance(b, dict): return None
    b = dict(b)
    t = str(b.get('type', 'para')).strip().lower().replace(' ', '_')
    t = TYPE_ALIASES.get(t, t)
    if mode == 'gate': t = {'worked_example': 'example', 'pitfall': 'trap'}.get(t, t)
    else: t = {'example': 'worked_example', 'trap': 'pitfall', 'callout': 'note', 'code': 'note'}.get(t, t)
    if t == 'image': return None
    b['type'] = t
    if t in FIELD: _alias(b, FIELD[t])
    if t in ('para', 'subhead', 'callout', 'trap', 'situation', 'concept', 'pitfall', 'note') and not isinstance(b.get('text', ''), str): b['text'] = _text(b['text'])
    if t in ('bullets', 'numbered'):
        items = b.get('items')
        b['items'] = [_text(x) for x in (items if isinstance(items, list) else [items] if items else [])]
    if t == 'formula':
        b['latex'] = re.sub(r'^\s*(\$\$?|\\\[)|(\$\$?|\\\])\s*$', '', _text(b.get('latex')))
    if t == 'table':
        _alias(_alias(b, 'header'), 'rows')
        rows, head = b.get('rows') or [], b.get('header') or []
        if rows and isinstance(rows[0], dict):
            head = head or list(rows[0]); rows = [[r.get(h, '') for h in head] for r in rows]
        b['header'], b['rows'] = [_text(h) for h in head], [[_text(c) for c in r] if isinstance(r, list) else [_text(r)] for r in rows]
    if t == 'example':
        _alias(_alias(b, 'problem'), 'solution')
        for k in ('problem', 'solution'):
            if isinstance(b.get(k), list): b[k] = [x for x in (block(v, mode) for v in b[k]) if x]
            elif b.get(k) is not None and not isinstance(b[k], str): b[k] = _text(b[k])
    if t == 'worked_example' and not b.get('text') and (b.get('problem') or b.get('solution')):
        b['text'] = _text(b.pop('problem', '')) + ('\n\n**Solution.** ' + _text(b.pop('solution')) if b.get('solution') else '')
    if t == 'quick_check':
        b['items'] = [{'q': _text(x.get('q') or x.get('question')), 'a': _text(x.get('a') or x.get('answer'))} for x in b.get('items') or [] if isinstance(x, dict)]
    if t == 'figure':
        if isinstance(b.get('figure'), dict): b.update(b.pop('figure'))
        b['kind'] = str(b.get('kind', '')).lower()
        if not isinstance(b.get('spec'), dict):
            b['spec'] = {k: v for k, v in b.items() if k not in ('type', 'kind', 'title', 'caption', 'width', 'spec')}
    if isinstance(b.get('blocks'), list): b['blocks'] = [x for x in (block(v, mode) for v in b['blocks']) if x]
    return b


def blocks(bs, mode):
    if isinstance(bs, str): bs = [bs]
    return [x for x in (block(b, mode) for b in bs or []) if x]


def answer_range(ans):
    """GATE NAT keys: the exact value for an integer, +-1 in the last decimal place otherwise."""
    s = str(ans).strip()
    if not re.fullmatch(r'-?\d+(\.\d+)?', s): return None
    if '.' not in s: return f'{s} to {s}'
    step = 10 ** -len(s.split('.')[1]); v = float(s)
    return f'{v - step:.{len(s.split(".")[1])}f} to {v + step:.{len(s.split(".")[1])}f}'


def widen(rng, ans):
    """A NAT range at least +-0.1 % of the answer wide, so the usual approximations (9550 for 60000/2pi, pi = 3.14) still score."""
    try:
        lo, hi = sorted(float(x) for x in str(rng).split(' to ')); v = float(ans)
    except (ValueError, TypeError): return rng
    d = len(str(ans).split('.')[1]) if '.' in str(ans) else 0
    half = 0.001 * abs(v)
    if hi - lo >= 2 * half: return rng
    return f'{min(lo, v - half):.{d}f} to {max(hi, v + half):.{d}f}'


def question(q, mode='gate'):
    """One GATE question, tidied: type, marks, options as a list of four, answer as letters or a number."""
    if not isinstance(q, dict): return q
    q = dict(q)
    for field, alts in (('question', ('stem', 'text', 'q', 'prompt')), ('solution', ('explanation', 'working', 'solution_text')),
                        ('options', ('choices',)), ('answer', ('correct', 'correct_answer', 'key'))):
        if q.get(field) in (None, '', []):
            for a in alts:
                if q.get(a) not in (None, '', []): q[field] = q.pop(a); break
    t = str(q.get('qtype') or q.get('type') or '').upper()
    q['qtype'] = 'MSQ' if 'MSQ' in t or 'MULTI' in t else 'NAT' if any(x in t for x in ('NAT', 'NUM', 'INTEGER')) else 'MCQ' if t else ('NAT' if not q.get('options') else 'MCQ')
    q.pop('type', None)
    m = re.search(r'[12]', str(q.get('marks', '')))
    if m: q['marks'] = int(m.group())
    opts = q.get('options')
    if isinstance(opts, dict): opts = [opts[k] for k in sorted(opts)]
    if isinstance(opts, list): q['options'] = [re.sub(r'^\s*\(?[A-Da-d][).:]\s+', '', _text(o)) for o in opts]
    if q['qtype'] == 'NAT':
        q.pop('options', None)
        m = re.search(r'-?\d+(\.\d+)?', str(q.get('answer', '')).replace('−', '-'))
        if m: q['answer'] = m.group()
        r = q.get('answer_range')
        if isinstance(r, (list, tuple)) and len(r) == 2: q['answer_range'] = f'{r[0]} to {r[1]}'
        elif isinstance(r, str) and re.fullmatch(r'\s*-?[\d.]+\s*[-–]\s*-?[\d.]+\s*', r): q['answer_range'] = re.sub(r'\s*[-–]\s*(?=-?[\d.]+\s*$)', ' to ', r.strip())
        if not q.get('answer_range') and q.get('answer') is not None: q['answer_range'] = answer_range(q['answer'])
        q['answer_range'] = widen(q.get('answer_range'), q.get('answer'))
    else:
        a = q.get('answer')
        if isinstance(a, int) and 1 <= a <= 4: a = 'ABCD'[a - 1]
        if isinstance(a, list): a = ', '.join(map(str, a))
        a = str(a or '')
        if q.get('options') and a.strip() in q['options']: a = 'ABCD'[q['options'].index(a.strip())]
        letters = sorted(set(re.findall(r'\b([A-D])\b', re.sub(r'(?i)\boption\s*', '', a.upper()))))
        if letters: q['answer'] = ', '.join(letters)
    if isinstance(q.get('solution'), list): q['solution'] = blocks(q['solution'], mode)
    for k in ('image', 'solution_image'): q.pop(k, None)
    if isinstance(q.get('figure'), dict): q['figure'] = block(dict(q['figure'], type='figure'), mode)
    if isinstance(q.get('solution_figure'), dict): q['solution_figure'] = block(dict(q['solution_figure'], type='figure'), mode)
    return q


def _first(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, '', []): return d[k]
    return None


def gate_plan(p):
    p = clean(p if isinstance(p, dict) else {})
    p['sections'] = [s if isinstance(s, dict) else {'heading': str(s)} for s in (_first(p, 'sections', 'outline') or [])]
    for s in p['sections']:
        s['heading'] = _text(_first(s, 'heading', 'title', 'name') or '')
        s['figure'] = _text(s.get('figure') or '')
    p['objectives'] = [_text(x) for x in p.get('objectives') or []]
    p['prerequisites'] = [_text(x) for x in p.get('prerequisites') or []]
    return p


def gate_notes(out):
    out = clean(out if isinstance(out, dict) else {})
    notes = _first(out, 'notes', 'sections') or []
    out = {'notes': [{'heading': _text(_first(n, 'heading', 'title') or ''), 'blocks': blocks(_first(n, 'blocks', 'content'), 'gate'),
                      **({'no_example': True} if n.get('no_example') else {})} for n in notes if isinstance(n, dict)]}
    return out


def align_notes(out, sections):
    """One note per planned section, in the plan's order, matched by heading (by position when only the headings differ).
    A section the model left out comes back with no blocks, so the repair writes just that one."""
    key = lambda s: re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()
    notes, aligned, used = out['notes'], [], set()
    for i, s in enumerate(sections):
        free = {key(n['heading']): j for j, n in enumerate(notes) if j not in used and n['heading']}
        close = difflib.get_close_matches(key(s['heading']), list(free), n=1, cutoff=0.6)
        j = free[close[0]] if close else i if len(notes) == len(sections) and i not in used else None
        if j is not None: used.add(j)                        # each returned section is used once
        aligned.append({**(notes[j] if j is not None else {'blocks': []}), 'heading': s['heading']})
    return {'notes': aligned}


def _lines(x):
    """traps / revision card lines: strings, from strings or {title, text} dicts."""
    return [(f"**{d.get('title')}:** {d.get('text', '')}" if isinstance(d, dict) and d.get('title') else _text(d)) for d in (x or []) if d]


def gate_questions(out):
    out = clean(out if isinstance(out, dict) else {})
    practice = [question(q) for q in _first(out, 'practice', 'practice_questions') or [] if isinstance(q, dict)]
    for i, q in enumerate(practice):            # smaller models write "easy" or leave the level out; the prompt orders Easy -> Hard
        lvl = str(q.get('level', '')).strip().capitalize()
        q['level'] = lvl if lvl in LEVELS else LEVELS[i * 3 // len(practice)]
        q.pop('source', None)
    practice.sort(key=lambda q: LEVELS.index(q['level']))
    sp = _first(out, 'sample_paper', 'sample') or {}
    if isinstance(sp, list): sp = {'questions': sp}
    sp = dict(sp); sp['questions'] = [question(q) for q in sp.get('questions') or [] if isinstance(q, dict)]
    for q in sp['questions']: q.pop('source', None); q.pop('level', None)
    sp['marks'] = sum(q.get('marks', 0) for q in sp['questions'] if isinstance(q.get('marks'), int))
    sp.setdefault('title', 'Sample paper (timed)'); sp.setdefault('duration', f"{round(sp['marks'] * 1.5)} min")
    return {'practice': practice, 'sample_paper': sp, 'traps': _lines(out.get('traps')), 'revision_card': _lines(_first(out, 'revision_card', 'revision'))}


def pyq_questions(out):
    return {'questions': [question(q) for q in (out.get('questions') if isinstance(out, dict) else None) or [] if isinstance(q, dict)]}


def nongate_plan(p):
    p = clean(p if isinstance(p, dict) else {})
    p['topics'] = [t if isinstance(t, dict) else {'title': str(t)} for t in p.get('topics') or []]
    for t in p['topics']: t['title'] = _text(_first(t, 'title', 'name') or '')
    return p


def nongate_topics(out):
    out = clean(out if isinstance(out, dict) else {})
    return {'topics': [{'blocks': blocks(_first(t, 'blocks', 'content') if isinstance(t, dict) else t, 'nongate')} for t in out.get('topics') or []]}


def nongate_end(out):
    out = clean(out if isinstance(out, dict) else {})
    cs = out.get('case_study')
    if isinstance(cs, dict):
        paras = cs.get('paragraphs') or cs.get('sections') or ([cs['text']] if cs.get('text') else [])
        cs['paragraphs'] = [p if isinstance(p, dict) else {'text': _text(p)} for p in paras]
        for p in cs['paragraphs']: p['text'] = _text(p.get('text') or p.get('content'))
        cs['title'] = _text(cs.get('title') or 'Case study'); cs['discussion'] = _text(cs.get('discussion') or '')
    practice = [{'tag': _text(p.get('tag', '')), 'question': _text(_first(p, 'question', 'q')), 'answer': _text(_first(p, 'answer', 'a', 'model_answer'))}
                for p in out.get('practice') or [] if isinstance(p, dict)]
    rev = out.get('revision')
    if isinstance(rev, dict):
        rev['concepts'] = [{'title': _text(c.get('title')), 'points': [_text(x) for x in c.get('points') or ([c['text']] if c.get('text') else [])]}
                           for c in rev.get('concepts') or [] if isinstance(c, dict)]
        rev['mistakes'] = [{'title': _text(m.get('title')), 'text': _text(m.get('text'))} for m in rev.get('mistakes') or [] if isinstance(m, dict)]
        rev['checklist'] = [_text(x) for x in rev.get('checklist') or []]
        d = rev.get('distinctions')
        if isinstance(d, dict): rev['distinctions'] = block(dict(d, type='table'), 'nongate')
        elif d: rev.pop('distinctions')
    return {'case_study': cs if isinstance(cs, dict) else None, 'practice': practice, 'revision': rev if isinstance(rev, dict) else None}


# ---------------------------------------------------------------- problems
def number(x):
    """A number from an answer: 11788, '2.5', '0x2E0C', '2E0C_H', '1 to 2' (first value)."""
    s = str(x).strip().replace(',', '').replace('−', '-')
    m = re.fullmatch(r'(?i)0x([0-9a-f]+)|([0-9a-f]+)\s*(?:_\{?h\}?|h|\(hex\))', s)
    if m: return int(m.group(1) or m.group(2), 16)
    m = re.search(r'-?\d+(\.\d+)?(e-?\d+)?', s)
    if not m: raise ValueError(f'no number in {x!r}')
    return float(m.group())


def check_mismatch(chk, answer=None, answer_range=None):
    """None when the arithmetic check reproduces the stated answer, else what is wrong."""
    expr = chk.get('expr') if isinstance(chk, dict) else chk
    stated = chk.get('answer', answer) if isinstance(chk, dict) else answer
    try: v = float(safe_eval(expr))
    except Exception as e: return f'its "check" expression {str(expr)[:60]!r} cannot be evaluated ({e}); write plain arithmetic'
    try:
        if answer_range and ' to ' in str(answer_range):
            lo, hi = sorted(number(x) for x in str(answer_range).split(' to '))
            if lo - 1e-9 <= v <= hi + 1e-9: return None
            return f'its "check" expression gives {v:g}, outside the answer range {answer_range}: recompute the answer'
        a = number(stated)
    except ValueError: return f'the stated answer {str(stated)[:40]!r} is not a number the check can compare'
    dec = re.search(r'\.(\d+)', str(stated))
    if abs(v - a) <= 0.5 * 10 ** -(len(dec.group(1)) if dec else 0) + 1e-9: return None     # equal up to the rounding of the stated answer
    return f'its "check" expression {str(expr)[:60]!r} gives {v:g}, but the stated answer is {stated}: recompute the working and the answer'


def math_problems(x, path):
    """A $ without its partner, or LaTeX environments that cannot be drawn (the drawing check catches the rest)."""
    out = []
    if isinstance(x, dict):
        if x.get('type') == 'code': return []
        for k, v in x.items():
            if k in ('spec', 'kind', 'check'): continue
            if k == 'latex' and isinstance(v, str) and BAD_TEX.search(tex_normalize(v)):
                out.append((path + (k,), f'the formula uses {BAD_TEX.search(tex_normalize(v)).group(0)!r}, which cannot be drawn: split it into several formula blocks or a table', True))
            else: out += math_problems(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x): out += math_problems(v, path + (i,))
    elif isinstance(x, str):
        parts = re.split(r'(?<!\\)\$', x)
        if len(parts) % 2 == 0: out.append((path, f'unbalanced $ in "{x[:60]}": every maths expression needs an opening and a closing $ (write a literal dollar as \\$)', True))
        else: out += [(path, f'the maths uses {BAD_TEX.search(tex_normalize(m)).group(0)!r}, which cannot be drawn: use plain text, several formula blocks or a table', True) for m in parts[1::2] if BAD_TEX.search(tex_normalize(m))]
    return out


RAW_JSON = re.compile(r'"(?:type|ref|latex|blocks|value|heading)"\s*:|(?:\]\}|\}\]){6,}')


def raw_json(x):
    """True when text holds JSON the model leaked into it (a broken repair, or a block written as text)."""
    if isinstance(x, str): return bool(RAW_JSON.search(x))
    if isinstance(x, dict): return any(raw_json(v) for k, v in x.items() if k not in ('spec', 'check'))
    return isinstance(x, list) and any(raw_json(v) for v in x)


CONSTANTS = {0.5, 1, 2, 3, 4, 8, 10, 16, 32, 60, 100, 180, 360, 1000, 9550, 1e3, 1e6, 1e9, 1e12, 1e-3, 1e-6, 1e-9}
NUM = r'(?<![\w.])\d+(?:\.\d+)?(?:[eE]-?\d+)?'


def _digits(v):
    """The significant digits of a number: 0.04, 40 and 4e1 all give '4'; 80e9 gives '8'."""
    return f'{abs(v):.6e}'.split('e')[0].replace('.', '').rstrip('0') or '0'


def missing_data(chk, given):
    """Round numbers (data such as G = 80e9 or d = 0.04) that a check uses but the question or problem never states."""
    expr = str(chk.get('expr') if isinstance(chk, dict) else chk)
    expr = re.sub(r'\*\*\s*(\([^()]*\)|[\d.]+)', '', expr)          # powers and roots (**2, **0.25, **(1/3)) are not data
    stated = {_digits(float(n)) for n in re.findall(NUM, given)}
    out = [n for n in re.findall(NUM, expr) if not (float(n) in CONSTANTS or abs(float(n) - 3.14159) < 0.01
                                                     or len(_digits(float(n))) > 2 or _digits(float(n)) in stated)]
    if not out: return None
    return (f'the check uses {", ".join(dict.fromkeys(out))}, which the question does not state: if it is data (a modulus, length, limit, '
            'diameter...), state it in the question text with its unit; if it is derived, write the check from the given values')


def block_problems(bs, allowed, path):
    out = []
    for i, b in enumerate(bs):
        p = path + (i,); t = b.get('type')
        if raw_json(b): out.append((p, 'this block contains raw JSON text instead of content: write it as proper blocks', True)); continue
        if t not in allowed: out.append((p, f'unknown block type {t!r}; use one of {sorted(allowed)}', True))
        elif t in FIELD and not b.get(FIELD[t]): out.append((p, f'a "{t}" block needs a non-empty "{FIELD[t]}" field', True))
        elif t == 'table' and not (b.get('header') and b.get('rows')): out.append((p, 'a table needs "header" and "rows"', True))
        elif t == 'figure' and b.get('kind') not in FIGURE_KINDS: out.append((p, f'figure kind {b.get("kind")!r} does not exist; use one of {sorted(FIGURE_KINDS)}', True))
        elif t == 'example' and not b.get('problem'): out.append((p, 'an example needs a "problem" and a "solution"', True))
        elif t in ('example', 'worked_example') and b.get('check'):
            m = check_mismatch(b['check']) or missing_data(b['check'], json.dumps(b.get('problem') or b.get('text') or '', ensure_ascii=False))
            if m: out.append((p, 'the worked example: ' + m, False))
        if t == 'quick_check' and not all(x.get('q') and x.get('a') for x in b.get('items') or []): out.append((p, 'quick_check items need "q" and "a"', True))
        if isinstance(b.get('blocks'), list): out += [(p, m, h) for _, m, h in block_problems(b['blocks'], allowed, p + ('blocks',))]
        for k in ('problem', 'solution'):
            if isinstance(b.get(k), list): out += [(p, m, h) for _, m, h in block_problems(b[k], allowed, p + (k,))]
    return out


def drawing_problems(obj):
    """Figures and maths that do not draw, found by drawing them in a subprocess exactly as the renderer will."""
    path = os.path.join(tempfile.mkdtemp(), 'content.json')
    json.dump(obj, open(path, 'w', encoding='utf-8'))
    try: r = subprocess.run([sys.executable, os.path.join(RENDER, 'check_content.py'), path], capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired: return []
    if r.returncode: return []          # the checker itself failed: the renderer's own fallbacks still apply
    return [(item_path(f['path']), ('this figure cannot be drawn: ' if f['what'] == 'figure' else '') + f['error'], f['what'] == 'figure')
            for f in json.loads(r.stdout)]


def walk_blocks(bs):
    for b in bs or []:
        if isinstance(b, dict):
            yield b
            for k in ('problem', 'solution', 'blocks'):
                if isinstance(b.get(k), list): yield from walk_blocks(b[k])


def gate_plan_problems(p):
    s = p.get('sections')
    if not (isinstance(s, list) and 3 <= len(s) <= 12 and all(x.get('heading') for x in s) and p.get('objectives')):
        return [((), 'need 3 to 12 "sections", each with a "heading", and "objectives"', True)]
    return []


def _numbers(x):
    return [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?(?:[eE]-?\d+)?', json.dumps(x, ensure_ascii=False))]


def _figures_and_text(parts):
    """The figures inside an example's problem/solution, and everything else in it."""
    parts = [p for p in parts if p]
    figs = [b for p in parts if isinstance(p, list) for b in walk_blocks(p) if b.get('type') == 'figure']
    rest = [b for p in parts for b in (p if isinstance(p, list) else [p]) if not (isinstance(b, dict) and b.get('type') == 'figure')]
    return figs, rest


def figure_problems(f, path, example_text=None):
    """A figure that cannot teach anything: data from another example, no axis labels, or a two-node diagram."""
    spec, kind, out = f.get('spec') or {}, f.get('kind'), []
    if kind in ('plot', 'bars') and not (spec.get('xlabel') or spec.get('ylabel') or f.get('title') or spec.get('title') or f.get('caption')):
        out.append((path, f'the {kind} figure has no axis labels, title or caption: label what is plotted, with units', False))
    if kind == 'graph' and len(spec.get('nodes') or []) < 3:
        out.append((path, 'a diagram of one or two nodes tells the student nothing: draw what the section needs (a plot, beam, circuit...) or leave it out', False))
    if example_text is not None:
        have = [abs(v) for v in _numbers(example_text) if v]
        data = [abs(v) for v in _numbers(spec) if abs(v) > 10 and v not in CONSTANTS]
        if len(data) >= 2 and not any(abs(v - h) <= 0.02 * h for v in data for h in have):
            out.append((path, 'the figure inside this worked example does not use any of the example\'s values: draw it from the example\'s own data', False))
    return out


def example_problems(b, path):
    """A numerical worked example (it has a "check") that is only a plug-in: almost no working shown. Conceptual examples
    reason in words and are not counted."""
    figs, rest = _figures_and_text([b.get('problem'), b.get('solution')])
    sol = b.get('solution')
    formulas = sum(1 for x in (sol if isinstance(sol, list) else []) if isinstance(x, dict) and x.get('type') in ('formula', 'table'))
    if b.get('check') and formulas < 2 and json.dumps(sol, ensure_ascii=False).count('=') < 3:
        out = [(path, 'the worked example shows almost no working: make it a GATE 2-mark problem solved in 3 or more steps with the intermediate values', False)]
    else: out = []
    return out + [p for f in figs for p in figure_problems(f, path, rest)]


def gate_notes_problems(out, sections):
    notes = out['notes']
    if len(notes) != len(sections) or not any(n['blocks'] for n in notes):
        return [((), f'"notes" must be a list of the {len(sections)} sections given, in the order given, each with its blocks', True)]
    probs = []
    for i, (n, s) in enumerate(zip(notes, sections)):
        if not n['blocks']:
            probs.append((('notes', i), 'this section is missing: write it in full as the plan describes it: ' + json.dumps(s, ensure_ascii=False), True)); continue
        probs += block_problems(n['blocks'], GATE_BLOCKS, ('notes', i, 'blocks'))
        probs += [(item_path(p), m, h) for p, m, h in math_problems(n['blocks'], ('notes', i, 'blocks'))]
        bl = list(walk_blocks(n['blocks']))
        if not n.get('no_example') and not any(b.get('type') == 'example' for b in bl):
            probs.append((('notes', i), 'this section needs one GATE-style worked example (an "example" block)', False))
        if s.get('figure') and not any(b.get('type') == 'figure' for b in bl):
            probs.append((('notes', i), f'the plan asks for a figure in this section ({s["figure"][:80]}): add a "figure" block', False))
        for j, b in enumerate(n['blocks']):          # examples with their figures; figures outside examples on their own
            if b.get('type') == 'example': probs += example_problems(b, ('notes', i, 'blocks', j))
            elif b.get('type') == 'figure': probs += figure_problems(b, ('notes', i, 'blocks', j))
    return probs + drawing_problems(out)


def _question_paths(msg):
    m = re.match(r'(P|S)(\d+):', msg)
    if not m: return None
    return ('practice', int(m.group(2)) - 1) if m.group(1) == 'P' else ('sample_paper', 'questions', int(m.group(2)) - 1)


def question_checks(q, path):
    """The answer check of one question: the arithmetic must reproduce the key (NAT) or the number in the correct option (MCQ),
    from data the question states. Also: no raw JSON leaked into the question."""
    if raw_json(q): return [(path, 'this question contains raw JSON text: write it again as a proper question', True)]
    if q.get('qtype') == 'MSQ' and q.get('options') and all(re.fullmatch(r'\s*[A-D](\s*,\s*[A-D])*\s*', o) for o in q['options']):
        return [(path, 'an MSQ has the four statements themselves as its options (A) to (D) and its answer is the correct letters ("A, C"): '
                       'do not list statements in the question and letter combinations as options', True)]
    if not q.get('check'): return []
    gap = missing_data(q['check'], json.dumps([q.get('question'), q.get('options'), q.get('figure')], ensure_ascii=False))
    out = [(path, gap, False)] if gap else []
    if q.get('qtype') == 'NAT': m = check_mismatch(q['check'], q.get('answer'), q.get('answer_range'))
    elif q.get('qtype') == 'MCQ' and q.get('options') and re.fullmatch(r'[A-D]', str(q.get('answer', ''))):
        opt = q['options']['ABCD'.index(q['answer'])]
        try: number(opt)
        except ValueError: return out
        m = check_mismatch(q['check'], opt)
    else: return out
    return out + ([(path, m, True)] if m else [])


def gate_questions_problems(out, paper):
    pr, sp = out['practice'], out['sample_paper']
    if len(pr) < 6 or len(sp['questions']) < 3: return [((), 'need 10 to 12 practice questions and a sample paper of 5 questions', True)]
    probs = [(p, m, True) for m in gate_check({'paper': paper, 'practice': pr, 'sample_paper': sp})[0] if (p := _question_paths(m))]
    stems = {q.get('question') for q in pr}
    probs += [(('sample_paper', 'questions', i), 'this sample-paper question repeats a practice question: write a different one', True)
              for i, q in enumerate(sp['questions']) if q.get('question') in stems]
    for i, q in enumerate(pr): probs += question_checks(q, ('practice', i))
    for i, q in enumerate(sp['questions']): probs += question_checks(q, ('sample_paper', 'questions', i))
    if not out['traps']: probs.append((('traps',), 'write 5 to 10 traps', False))
    if not out['revision_card']: probs.append((('revision_card',), 'write 5 to 8 revision-card lines', False))
    probs += [(item_path(p), m, h) for p, m, h in math_problems({k: out[k] for k in ('practice', 'sample_paper', 'traps', 'revision_card')}, ())]
    return probs + drawing_problems(out)


def nongate_plan_problems(p):
    if p.get('title') and p['topics'] and all(t['title'] for t in p['topics']): return []
    return [((), 'need "title" and a non-empty "topics" list, each with a "title"', True)]


def nongate_topics_problems(out, n):
    if len(out['topics']) != n: return [((), f'"topics" must be a list of exactly {n} entries, in the order given', True)]
    probs = []
    for i, t in enumerate(out['topics']):
        if not t['blocks']: probs.append((('topics', i), 'this topic has no blocks: write it', True)); continue
        probs += block_problems(t['blocks'], NONGATE_BLOCKS, ('topics', i, 'blocks'))
        probs += [p for j, b in enumerate(t['blocks']) if b.get('type') == 'figure' for p in figure_problems(b, ('topics', i, 'blocks', j))]
        probs += [(item_path(p), m, h) for p, m, h in math_problems(t['blocks'], ('topics', i, 'blocks'))]
    return probs + drawing_problems(out)


def nongate_end_problems(out):
    if not out['practice'] or not all(p['question'] and p['answer'] for p in out['practice']):
        return [((), '"practice" must be a list of {tag, question, answer}, each with a question and an answer', True)]
    probs = [(item_path(p), m, h) for p, m, h in math_problems(out, ())]
    if out['case_study'] and not out['case_study']['paragraphs']: probs.append((('case_study',), 'the case study needs "paragraphs"', True))
    return probs + drawing_problems(out)

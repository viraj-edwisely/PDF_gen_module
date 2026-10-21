"""Content rules shared by the pipeline: tidy a model reply, find its problems, and edit it by path.

A model reply goes through   tidy (fix predictable slips in code)  ->  problems (what is still wrong)  ->  the pipeline
sends only the broken items back to the model, and drops what stays broken.

A problem is (path, message, hard):
- path ()            the reply as a whole is unusable (wrong shape): the model is asked again from scratch;
- path ('notes', 2, 'blocks', 4) or ('practice', 6) ...   one item: only that item goes back for repair;
- hard=True          the item is broken and is dropped if the repair does not fix it;
- hard=False         a requirement (a missing worked example or figure, a wrong answer check): kept, with a warning.
"""
import difflib, json, math, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, 'render')
sys.path.insert(0, RENDER)
from check_gate_level import check as gate_check, key_formulas   # noqa: E402  (pure Python)
from safe_eval import safe_eval                     # noqa: E402  (numpy only)
from tex import normalize as tex_normalize      # noqa: E402  (pure Python)
from llm import loads                               # noqa: E402  (json.loads that keeps LaTeX backslashes)

GATE_BLOCKS = {'para', 'subhead', 'bullets', 'numbered', 'formula', 'table', 'example', 'trap', 'note', 'callout', 'code', 'figure', 'spacer', 'pagebreak'}
NONGATE_BLOCKS = {'situation', 'concept', 'worked_example', 'pitfall', 'note', 'quick_check', 'para', 'table', 'bullets', 'numbered', 'formula', 'figure', 'subhead'}
FIGURE_KINDS = {'gantt', 'timeline', 'plot', 'bars', 'graph', 'cells', 'circuit', 'geometry', 'block', 'logic', 'mermaid',
                'beam', 'mohr', 'pressure', 'waveform', 'spectrum', 'cycle', 'control', 'illustration'}
FIELD = {'para': 'text', 'subhead': 'text', 'bullets': 'items', 'numbered': 'items', 'formula': 'latex', 'code': 'text', 'callout': 'text',
         'trap': 'text', 'situation': 'text', 'concept': 'text', 'pitfall': 'text', 'worked_example': 'text', 'quick_check': 'items'}
ALIASES = {'text': ('content', 'body', 'value', 'paragraph', 'description', 'statement', 'code'), 'items': ('list', 'points', 'bullets', 'steps', 'entries', 'questions'),
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
    for path in sorted(set(map(tuple, paths)), key=lambda p: [(-x if isinstance(x, int) else 0) for x in p] + [1]):   # + [1]: inner paths first
        try:
            parent = get(obj, path[:-1])
            if isinstance(parent, list): del parent[path[-1]]
            else: parent.pop(path[-1], None)
        except (KeyError, IndexError, TypeError): pass


def item_path(path):
    """The repairable item that contains `path`: ['notes', 0, 'blocks', 3, 'problem', 1] -> ('notes', 0, 'blocks', 3)."""
    path = list(path)
    if not path: return ()
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


def split_topic(text, subtopics=''):
    """A topic as typed, as (title, subtopics). Subtopics come from their own field (comma or semicolon separated) or, when
    that is empty, from a bracketed list at the end of the topic: "Buoyancy (Buoyant force, Metacentre, ...)" -> title
    "Buoyancy" and the list. A bracket without a list ("Kirchhoff's laws (KCL)") stays part of the title."""
    parts = lambda s: [x.strip() for x in re.split(r'[;,\n]', s) if x.strip()]
    text = ' '.join(str(text or '').split())
    m = re.fullmatch(r'(.+?)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)', text)
    if not subtopics and m and len(parts(m.group(2))) >= 2: return m.group(1).strip(), parts(m.group(2))
    return text, parts(subtopics or '')


# ---------------------------------------------------------------- tidy: fix predictable slips in code
def clean(x):
    """NUL characters out (the database refuses them); 'GATE 2027'-style target years out of printed text; escapes such as
    \\u0024 or \\u00bd that a model wrote out as text (double-escaped) back to their characters; \\( \\) and \\[ \\] maths to $...$."""
    if isinstance(x, str):
        x = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), x.replace('\x00', ''))
        x = x.encode('utf-16', 'surrogatepass').decode('utf-16', 'replace')     # a pair written as two escapes becomes one character
        x = re.sub(r'(?<!\\)\\\((.+?)(?<!\\)\\\)|(?<!\\)\\\[(.+?)(?<!\\)\\\]', lambda m: '$' + (m.group(1) or m.group(2)).strip() + '$', x, flags=re.S)
        return re.sub(r'\bGATE\s*20\d\d\b', 'GATE', x.replace('\x00', ''))
    if isinstance(x, list): return [clean(v) for v in x]
    if isinstance(x, dict):
        if x.get('type') == 'code': return {k: v.replace('\x00', '') if isinstance(v, str) else v for k, v in x.items()}    # code as written
        return {k: clean(v) if k != 'source' else v for k, v in x.items()}
    return x


def _alias(d, field):
    if d.get(field) in (None, '', []):
        for a in ALIASES.get(field, ()):
            if d.get(a) not in (None, '', []): d[field] = d.pop(a); break
    return d


def _list(x):
    """A list from whatever the model put where a list belongs: a list, a dict keyed 0, 1, 2 or A, B, C, a JSON list
    written as a string, a single item, or nothing."""
    if isinstance(x, list): return x
    if x is None or x == '' or x == {}: return []
    if isinstance(x, str) and x.strip().startswith('['):
        try: v = loads(x)
        except ValueError: v = None
        if isinstance(v, list): return v
    if isinstance(x, dict) and all(re.fullmatch(r'\d+|[A-Za-z]', str(k)) for k in x):
        return [x[k] for k in sorted(x, key=lambda k: (len(str(k)), str(k)))]
    return [x]


def _dict(x):
    """A dict from a dict or a JSON object written as a string; anything else is empty."""
    if isinstance(x, str) and x.strip().startswith('{'):
        try: x = loads(x)
        except ValueError: pass
    return x if isinstance(x, dict) else {}


def _text(x):
    """A string from whatever the model put there (a list of lines, a dict with text)."""
    if isinstance(x, list): return '\n\n'.join(_text(v) for v in x)
    if isinstance(x, dict): return _text(x.get('text') or x.get('content') or ' '.join(str(v) for v in x.values()))
    return '' if x is None else str(x)


STEP_KEYS = {'say': ('label', 'title', 'what', 'step', 'heading', 'find'), 'latex': ('formula', 'math', 'work', 'working', 'equation', 'expr'),
             'text': ('explanation', 'note', 'description', 'content'), 'result': ('value', 'answer', 'gives')}
TEX_ENDS = re.compile(r'^\s*(\$\$?|\\\[)|(\$\$?|\\\])\s*$')


def _steps(x, mode='gate'):
    """Solution steps from whatever the model wrote: a list of {say, latex, text, result, blocks} (fields under other names,
    strings, "1. ..." lines), or a solution string, which becomes one step per paragraph or numbered line."""
    if isinstance(x, str):
        x = [p for p in re.split(r'\n\s*\n|\n(?=\s*(?:\d+[.)]|Step\s*\d+)\s)', x) if p.strip()]
    out = []
    for st in _list(x):
        if isinstance(st, str): st = {'text': re.sub(r'^\s*(?:\d+[.)]|Step\s*\d+[:.]?)\s*', '', st)}
        if not isinstance(st, dict): continue
        st = dict(st)
        for k, alts in STEP_KEYS.items():
            if st.get(k) in (None, ''):
                for a in alts:
                    if st.get(a) not in (None, ''): st[k] = st.pop(a); break
            if k in st: st[k] = _text(st[k])
        if st.get('latex'): st['latex'] = TEX_ENDS.sub('', st['latex'])
        if isinstance(st.get('blocks'), list): st['blocks'] = blocks(st['blocks'], mode)
        if any(st.get(k) for k in ('say', 'latex', 'text', 'result', 'blocks')): out.append(st)
    return out


def _where(x):
    """Formula symbols as [symbol, meaning, unit] rows, from rows, {symbol: meaning} dicts, row dicts or "ρ = density (kg/m³)" strings."""
    if isinstance(x, dict) and not any(k in x for k in ('symbol', 'sym')): x = [[k, v] for k, v in x.items()]
    rows = []
    for r in _list(x):
        if isinstance(r, dict): r = [_text(r.get('symbol') or r.get('sym')), _text(r.get('meaning') or r.get('description') or r.get('name')), _text(r.get('unit') or r.get('units') or '')]
        elif isinstance(r, str):
            m = re.match(r'\s*(.+?)\s*(?:=|:|–|—|\bis\b)\s*(.+)', r)
            if not m: continue
            u = re.search(r'\(([^()]*)\)\s*$|,\s*in\s+(.+)$', m.group(2))
            r = [m.group(1), m.group(2)[:u.start()].strip() if u else m.group(2), (u.group(1) or u.group(2)) if u else '']
        elif isinstance(r, (list, tuple)): r = [_text(c) for c in r][:3]
        else: continue
        if r and r[0]: rows.append(r)
    return rows


SYMBOL_TABLE = re.compile(r'^\s*(symbol|notation|term|quantity)s?\s*$', re.I)


def symbol_tables_to_where(bs):
    """A Symbol / Meaning / Unit table right after a formula becomes that formula's "where" list (the model's own symbol
    tables doubled the length of a section and repeated symbols)."""
    out = []
    for b in bs:
        if isinstance(b, dict) and b.get('type') == 'table' and b.get('header') and SYMBOL_TABLE.match(str(b['header'][0])) and \
                out and isinstance(out[-1], dict) and out[-1].get('type') == 'formula':
            out[-1] = dict(out[-1], where=(out[-1].get('where') or []) + _where(b.get('rows')))
            continue
        out.append(b)
    return out


def block(b, mode):
    """One content block, tidied. Returns None for blocks that cannot be shown (images: the app draws all figures itself)."""
    if isinstance(b, str) and b.strip().startswith('{'):          # a block the model wrote as a string of JSON
        try: b = loads(b)
        except ValueError: pass
    if isinstance(b, str): return {'type': 'para', 'text': b}
    if not isinstance(b, dict): return None
    b = dict(b)
    t = str(b.get('type') or 'para').strip().lower().replace(' ', '_')
    t = TYPE_ALIASES.get(t, t)
    if mode == 'gate': t = {'worked_example': 'example', 'pitfall': 'trap'}.get(t, t)
    else: t = {'example': 'worked_example', 'trap': 'pitfall', 'callout': 'note', 'code': 'note'}.get(t, t)
    if t == 'image': return None
    b['type'] = t
    if t in FIELD: _alias(b, FIELD[t])
    if t in ('para', 'subhead', 'callout', 'trap', 'situation', 'concept', 'pitfall', 'note') and not isinstance(b.get('text', ''), str): b['text'] = _text(b['text'])
    if t in ('bullets', 'numbered'):
        b['items'] = [_text(x) for x in _list(b.get('items'))]
    if t == 'formula':
        b['latex'] = TEX_ENDS.sub('', _text(b.get('latex')))
        w = _first(b, 'where', 'symbols', 'variables', 'definitions', 'legend')
        for k in ('symbols', 'variables', 'definitions', 'legend'): b.pop(k, None)
        if w: b['where'] = _where(w)
        if 'key' in b: b['key'] = b['key'] in (True, 'true', 'yes', 1)
    if t == 'table':
        _alias(_alias(b, 'header'), 'rows')
        rows, head = _list(b.get('rows')), _list(b.get('header'))
        pick = lambda h, *ks: _text(next((h[k] for k in ks if h.get(k)), '') if isinstance(h, dict) else h)
        keys, head = [pick(h, 'key', 'field', 'name', 'label') for h in head], [pick(h, 'label', 'name', 'key', 'field') for h in head]
        if rows and isinstance(rows[0], dict):
            keys = keys or [str(k) for k in rows[0]]; head = head or keys
            rows = [[r.get(k, '') for k in keys] if isinstance(r, dict) else r for r in rows]
        b['header'], b['rows'] = head, [[_text(c) for c in r] if isinstance(r, list) else [_text(r)] for r in rows]
    if t == 'example':
        _alias(b, 'problem')
        sol = b.get('solution')
        if isinstance(sol, dict):                   # the structured solution written inside "solution"
            b.update({k: v for k, v in sol.items() if k in ('given', 'find', 'steps', 'answer', 'rushed') and not b.get(k)}); b.pop('solution')
        if not b.get('steps') and not b.get('solution'): _alias(b, 'solution')
        for k in ('problem', 'solution'):
            if isinstance(b.get(k), list): b[k] = [x for x in (block(v, mode) for v in b[k]) if x]
            elif b.get(k) is not None and not isinstance(b[k], str): b[k] = _text(b[k])
        if b.get('steps'): b['steps'] = _steps(b['steps'], mode)
        elif isinstance(b.get('solution'), str) and b['solution'].strip(): b['steps'] = _steps(b.pop('solution'), mode)    # old style: a paragraph per step
        b['given'] = [g if isinstance(g, (list, tuple)) else _text(g) for g in _list(b.get('given'))]
        for k in ('find', 'answer', 'rushed'):
            if b.get(k) is not None: b[k] = _text(b[k])
    if t == 'worked_example' and (isinstance(b.get('problem'), list) or isinstance(b.get('solution'), list)):
        sol = blocks(b.pop('solution', None), mode)
        b['blocks'] = blocks(b.pop('problem', None), mode) + ([{'type': 'para', 'text': '**Solution.**'}] + sol if sol else []) + _list(b.get('blocks'))
        b['text'] = b.get('text') or '**Problem.**'
    if t == 'worked_example' and not b.get('text') and (b.get('problem') or b.get('solution')):
        b['text'] = _text(b.pop('problem', '')) + ('\n\n**Solution.** ' + _text(b.pop('solution')) if b.get('solution') else '')
    if t != 'example':
        for k in ('problem', 'solution', 'steps', 'given', 'find', 'rushed'): b.pop(k, None)     # only examples have them (never drawn elsewhere)
    if t == 'quick_check':
        b['items'] = [{'q': _text(x.get('q') or x.get('question')), 'a': _text(x.get('a') or x.get('answer'))} for x in _list(b.get('items')) if isinstance(x, dict)]
    if t == 'figure':
        if isinstance(b.get('figure'), dict):
            fig = b.pop('figure'); b.update({k: v for k, v in fig.items() if k != 'type'})
            if not b.get('kind') and fig.get('type') not in (None, 'figure'): b['kind'] = fig['type']
        kind = str(b.get('kind') or '').strip().lower().replace(' ', '_')
        b['kind'] = {'bar': 'bars', 'bar_chart': 'bars', 'histogram': 'bars', 'line': 'plot', 'line_chart': 'plot', 'chart': 'plot',
                     'tree': 'graph', 'network': 'graph', 'diagram': 'graph', 'grid': 'cells', 'matrix': 'cells'}.get(kind, kind)
        if not isinstance(b.get('spec'), dict):
            b['spec'] = {k: v for k, v in b.items() if k not in ('type', 'kind', 'title', 'caption', 'width', 'spec')}
    if isinstance(b.get('blocks'), list): b['blocks'] = [x for x in (block(v, mode) for v in b['blocks']) if x]
    return b


def blocks(bs, mode):
    return symbol_tables_to_where([x for x in (block(b, mode) for b in _list(bs)) if x])


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
    if '.' not in str(ans): return rng                 # a whole-number key (a count, an address) is exact in GATE
    d = len(str(ans).split('.')[1])
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
    q['qtype'] = 'MSQ' if re.search(r'MSQ|SELECT|MULTIPLE[\s_-]*(CORRECT|ANSWER|RESPONSE)', t) else 'NAT' if any(x in t for x in ('NAT', 'NUM', 'INTEGER')) else 'MCQ' if t else ('NAT' if not q.get('options') else 'MCQ')
    q.pop('type', None)
    m = re.search(r'[12]', str(q.get('marks', '')))
    if m: q['marks'] = int(m.group())
    else: q.pop('marks', None)                                  # "two", None, True: the checker reports the missing marks
    q['question'] = _text(q.get('question'))
    if q.get('solution') is not None and not isinstance(q['solution'], (str, list)): q['solution'] = _text(q['solution'])
    opts = q.get('options')
    if isinstance(opts, str) and re.search(r'\(?\b[A-D][).:]\s', opts):      # "A) x  B) y  C) z  D) w" in one string
        opts = [o for o in re.split(r'(?:^|\s)\(?[A-D][).:]\s+', opts) if o.strip()]
    opts = _list(opts) if opts not in (None, '') else None
    if opts: q['options'] = [re.sub(r'^\s*\(?[A-Da-d][).:]\s+', '', _text(o)).strip() for o in opts]
    else: q.pop('options', None)
    if q['qtype'] == 'NAT':
        q.pop('options', None)
        a = str(q.get('answer', '')).replace('−', '-').replace(',', '').rsplit('=', 1)[-1]       # "2^10 = 1024": the value after the last =
        m = re.search(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?', a)
        if m and math.isfinite(float(m.group())): q['answer'] = (f'{float(m.group()):.10f}'.rstrip('0').rstrip('.') if re.search(r'[eE]|^-?\.', m.group()) else m.group())
        r = q.get('answer_range')
        if isinstance(r, (list, tuple)) and len(r) == 2: q['answer_range'] = f'{r[0]} to {r[1]}'
        elif isinstance(r, str) and re.fullmatch(r'\s*-?[\d.]+\s*[-–]\s*-?[\d.]+\s*', r): q['answer_range'] = re.sub(r'\s*[-–]\s*(?=-?[\d.]+\s*$)', ' to ', r.strip())
        if not q.get('answer_range') and q.get('answer') is not None: q['answer_range'] = answer_range(q['answer'])
        q['answer_range'] = widen(q.get('answer_range'), q.get('answer'))
    else:
        a = q.get('answer')
        if isinstance(a, int) and 1 <= a <= 4: a = 'ABCD'[a - 1]
        if isinstance(a, list): a = ', '.join(map(str, a))
        a = str(a or '').strip()
        opts = q.get('options') or []
        if a in opts and opts.index(a) < 4: a = 'ABCD'[opts.index(a)]
        key = re.sub(r'(?i)\boption\s*', '', a)
        if re.fullmatch(r'(?i)\s*\(?[A-D]\)?\.?(\s*(,|and|&|;|\s)\s*\(?[A-D]\)?\.?)*\s*', key): letters = re.findall(r'(?<![A-Za-z])[A-Da-d](?![A-Za-z])', key)
        else: letters = re.findall(r'^\(?([A-Da-d])[).:]', key)        # "B) 24 ms": the letter in front
        if letters: q['answer'] = ', '.join(sorted(set(x.upper() for x in letters)))
    if isinstance(q.get('solution'), list) and not any(isinstance(x, dict) and x.get('type') for x in q['solution']):
        q['steps'] = q.pop('solution')                 # steps written under "solution"
    if q.get('steps'): q['steps'] = _steps(q['steps'], mode)
    if isinstance(q.get('solution'), list): q['solution'] = blocks(q['solution'], mode)
    for k in ('image', 'solution_image'): q.pop(k, None)
    for k in ('figure', 'solution_figure'):
        if isinstance(q.get(k), dict): q[k] = block(dict(q[k], type='figure'), mode)
        else: q.pop(k, None)
    return q


def _first(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, '', []): return d[k]
    return None


def gate_plan(p):
    p = clean(p if isinstance(p, dict) else {})
    p['sections'] = [s if isinstance(s, dict) else {'heading': _text(s)} for s in _list(_first(p, 'sections', 'outline'))]
    for s in p['sections']:
        s['heading'] = _text(_first(s, 'heading', 'title', 'name') or '')
        s['figure'] = _text(s.get('figure') or '')
        for k in ('builds_on', 'no_figure_reason'): s[k] = _text(s.get(k) or '')
    p['storyline'] = _text(p.get('storyline'))
    p['coverage'] = [{'subtopic': _text(_first(c, 'subtopic', 'item', 'topic')), 'section': _text(_first(c, 'section', 'heading'))}
                     for c in _list(p.get('coverage')) if isinstance(c, dict)]
    p['notation'] = [{k: _text(_first(n, k, *alts) or '') for k, alts in (('symbol', ('sym',)), ('meaning', ('name', 'description')), ('unit', ('units',)),
                                                                          ('convention', ('sign', 'note')))} for n in _list(p.get('notation')) if isinstance(n, dict)]
    for k in ('subtitle', 'syllabus_line'): p[k] = _text(p.get(k))
    p['objectives'] = [_text(x) for x in _list(p.get('objectives'))]
    p['prerequisites'] = [_text(x) for x in _list(p.get('prerequisites'))]
    return p


def gate_notes(out):
    out = clean(out if isinstance(out, dict) else {})
    notes = _list(_first(out, 'notes', 'sections'))
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
    return [(f"**{d.get('title')}:** {d.get('text', '')}" if isinstance(d, dict) and d.get('title') else _text(d)) for d in _list(x) if d]


def gate_questions(out):
    out = clean(out if isinstance(out, dict) else {})
    practice = [question(q) for q in _list(_first(out, 'practice', 'practice_questions')) if isinstance(q, dict)]
    for i, q in enumerate(practice):            # smaller models write "easy" or leave the level out; the prompt orders Easy -> Hard
        lvl = str(q.get('level', '')).strip().capitalize()
        q['level'] = lvl if lvl in LEVELS else LEVELS[i * 3 // len(practice)]
        q.pop('source', None)
    practice.sort(key=lambda q: LEVELS.index(q['level']))
    sp = _first(out, 'sample_paper', 'sample')
    sp = {'questions': sp} if isinstance(sp, list) else dict(_dict(sp))
    sp['questions'] = [question(q) for q in _list(sp.get('questions')) if isinstance(q, dict)]
    for q in sp['questions']: q.pop('source', None); q.pop('level', None)
    sp['marks'] = sum(q.get('marks', 0) for q in sp['questions'] if isinstance(q.get('marks'), int))
    sp['title'] = _text(sp.get('title')) or 'Sample paper (timed)'; sp['duration'] = _text(sp.get('duration')) or f"{round(sp['marks'] * 1.5)} min"
    return {'practice': practice, 'sample_paper': sp, 'traps': _lines(out.get('traps')), 'revision_card': _lines(_first(out, 'revision_card', 'revision'))}


def notes_digest(notes):
    """The notes as the revision step sees them: per section its heading, key formulas, callouts and traps (first sentences)."""
    first = lambda t: re.split(r'(?<=[.!?])\s', _text(t), 1)[0][:220]
    out = []
    for n in notes:
        bl = list(walk_blocks(n.get('blocks', [])))
        out.append({'heading': n.get('heading', ''), 'key_formulas': key_formulas(n),
                    'rules': [first(b.get('text')) for b in bl if b.get('type') == 'callout'][:2],
                    'traps': [first(b.get('text')) for b in bl if b.get('type') == 'trap'][:2]})
    return out


def gate_revision(out, notes):
    """The revision page: one row per notes section (in order, under the notes' own headings) and the flow between them."""
    out = clean(out if isinstance(out, dict) else {})
    rows = [r for r in _list(_first(out, 'rows', 'revision', 'sections')) if isinstance(r, dict)]
    heads = [n.get('heading', '') for n in notes]
    tidy = [{k: TEX_ENDS.sub('', _text(_first(r, k, *alts) or '')) if k == 'formula' else _text(_first(r, k, *alts) or '')
             for k, alts in (('section', ('heading', 'title')), ('idea', ('summary', 'point')), ('formula', ('latex', 'key_formula')),
                             ('rule', ('remember', 'decision_rule')), ('trap', ('mistake', 'pitfall')))} for r in rows]
    if len(tidy) == len(heads):
        for r, h in zip(tidy, heads): r['section'] = h
    return {'rows': tidy, 'flow': [_text(x) for x in _list(out.get('flow')) if x][:8]}


def gate_revision_problems(out, notes):
    if len(out['rows']) != len(notes) or not all(r['idea'] for r in out['rows']):
        return [((), f'"rows" must have one entry per section ({len(notes)}), each with an "idea"', True)]
    return [(item_path(p), m, h) for p, m, h in math_problems(out, ())]


def revision_from_notes(notes):
    """A revision page without a model call (the fallback when the revision step fails): headings, key formulas, traps."""
    return {'rows': [{'section': d['heading'], 'idea': d['heading'], 'formula': (d['key_formulas'] or [''])[0],
                      'rule': (d['rules'] or [''])[0], 'trap': (d['traps'] or [''])[0]} for d in notes_digest(notes)], 'flow': []}


def retidy(c):
    """A finished GATE content JSON brought to the current structure (paragraph solutions become steps, symbol tables
    become "where" lists, the title loses its bracketed subtopics), for re-rendering an older PDF without the model."""
    c = dict(c)
    c['topic_name'], subs = split_topic(c.get('topic_name', ''), ', '.join(c.get('subtopics') or []))
    c['subtopics'] = subs
    c.update(gate_notes(c))
    levels = [q.get('level') for q in c.get('practice', [])]
    q = gate_questions(c)
    for x, lvl in zip(q['practice'], levels): x['level'] = lvl or x['level']
    c.update(practice=q['practice'], sample_paper={**(c.get('sample_paper') or {}), **q['sample_paper']})
    c['pyqs'] = [question(x) for x in c.get('pyqs') or [] if isinstance(x, dict)]
    return c


def pyq_questions(out):
    return {'questions': [question(q) for q in _list(out.get('questions') if isinstance(out, dict) else None) if isinstance(q, dict)]}


def nongate_plan(p):
    p = clean(p if isinstance(p, dict) else {})
    p['topics'] = [t if isinstance(t, dict) else {'title': _text(t)} for t in _list(p.get('topics'))]
    for t in p['topics']: t['title'] = _text(_first(t, 'title', 'name') or '')
    for k in ('title', 'description', 'study_time', 'audience'): p[k] = _text(p.get(k))
    return p


def nongate_topics(out):
    out = clean(out if isinstance(out, dict) else {})
    return {'topics': [{'blocks': blocks(_first(t, 'blocks', 'content') if isinstance(t, dict) else t, 'nongate')} for t in _list(out.get('topics'))]}


def nongate_end(out):
    out = clean(out if isinstance(out, dict) else {})
    cs = _dict(out.get('case_study')) or None
    if cs:
        paras = _list(cs.get('paragraphs') or cs.get('sections') or cs.get('text'))
        cs['paragraphs'] = [p if isinstance(p, dict) else {'text': _text(p)} for p in paras]
        for p in cs['paragraphs']: p['text'] = _text(p.get('text') or p.get('content'))
        cs['title'] = _text(cs.get('title') or 'Case study'); cs['discussion'] = _text(cs.get('discussion') or '')
    practice = [{'tag': _text(p.get('tag', '')), 'question': _text(_first(p, 'question', 'q')), 'answer': _text(_first(p, 'answer', 'a', 'model_answer'))}
                for p in _list(out.get('practice')) if isinstance(p, dict)]
    rev = _dict(out.get('revision')) or None
    if rev:
        rev['concepts'] = [{'title': _text(c.get('title')), 'points': [_text(x) for x in _list(c.get('points') or c.get('text'))]}
                           for c in _list(rev.get('concepts')) if isinstance(c, dict)]
        rev['mistakes'] = [{'title': _text(m.get('title')), 'text': _text(m.get('text'))} for m in _list(rev.get('mistakes')) if isinstance(m, dict)]
        rev['checklist'] = [_text(x) for x in _list(rev.get('checklist'))]
        d = rev.get('distinctions')
        if isinstance(d, dict): rev['distinctions'] = block(dict(d, type='table'), 'nongate')
        elif d: rev.pop('distinctions')
    return {'case_study': cs, 'practice': practice, 'revision': rev}


# ---------------------------------------------------------------- problems
def number(x):
    """A number from an answer: 11788, '2.5', '0x2E0C', '2E0C_H', '1 to 2' (first value)."""
    s = str(x).strip().replace(',', '').replace('−', '-')
    m = re.fullmatch(r'0[xX]([0-9a-fA-F]+)|([0-9a-fA-F]+)\s*(?:_\{?[hH]\}?|\(hex\))|([0-9A-F]*[A-F][0-9A-F]*)H', s)
    if m: return int(m.group(1) or m.group(2) or m.group(3), 16)
    m = re.search(r'-?\d+(\.\d+)?(e-?\d+)?', s)
    if not m: raise ValueError(f'no number in {x!r}')
    return float(m.group())


def check_mismatch(chk, answer=None, answer_range=None):
    """None when the arithmetic check reproduces the stated answer, else what is wrong."""
    expr = chk.get('expr') if isinstance(chk, dict) else chk
    stated = chk.get('answer', answer) if isinstance(chk, dict) else answer
    try: v = float(safe_eval(str(expr).replace('^', '**')))
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
    if isinstance(x, str): return bool(RAW_JSON.search(re.sub(r'`[^`]*`', '', x)))
    if isinstance(x, dict): return x.get('type') != 'code' and any(raw_json(v) for k, v in x.items() if k not in ('spec', 'check'))
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
        if not isinstance(b, dict): continue           # only blocks are checked (a stray list under a non-example block is never drawn)
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
            for f in json.loads(r.stdout)]          # maths that does not draw is shown as text, and overlapping labels are soft: both kept


def walk_blocks(bs):
    """Every block, at any depth: inside boxes, example problems and solutions, and the blocks of solution steps."""
    for b in bs or []:
        if isinstance(b, dict):
            yield b
            for k in ('problem', 'solution', 'blocks'):
                if isinstance(b.get(k), list): yield from walk_blocks(b[k])
            for st in b.get('steps') or []:
                if isinstance(st, dict) and isinstance(st.get('blocks'), list): yield from walk_blocks(st['blocks'])


def _key(t): return re.sub(r'[^a-z0-9]+', ' ', str(t).lower()).strip()


def gate_plan_problems(p, subtopics=()):
    """A usable plan, every subtopic the user listed taught by a section, and a figure or a reason for each section."""
    s = p.get('sections')
    if not (isinstance(s, list) and 3 <= len(s) <= 16 and all(x.get('heading') for x in s) and p.get('objectives')):
        return [((), 'need 3 to 16 "sections", each with a "heading", and "objectives"', True)]
    heads = {_key(x['heading']) for x in s}
    covered = {_key(c['subtopic']) for c in p.get('coverage', []) if _key(c['section']) in heads}
    words = lambda t: set(_key(t).split())
    missing = [t for t in subtopics if _key(t) not in covered and not any(words(t) <= words(c) or words(t) <= words(h) for c in covered for h in heads)]
    probs = [(('coverage',), 'these subtopics are not taught by any section: ' + '; '.join(missing) +
              '. Add a section for each (or name the section that teaches it), and list them in "coverage"', False)] if missing else []
    probs += [(('sections', i), f'section "{x["heading"]}" has no figure and no "no_figure_reason": plan the standard figure for it, or say why none helps', False)
              for i, x in enumerate(s) if not x.get('figure') and not x.get('no_figure_reason')]
    return probs


def _numbers(x):
    return [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?(?:[eE]-?\d+)?', json.dumps(x, ensure_ascii=False))]


def _figures_and_text(parts):
    """The figures inside an example's problem/solution, and everything else in it."""
    parts = [p for p in parts if p]
    figs = [b for p in parts if isinstance(p, list) for b in walk_blocks(p) if b.get('type') == 'figure']
    rest = [b for p in parts for b in (p if isinstance(p, list) else [p]) if not (isinstance(b, dict) and b.get('type') == 'figure')]
    return figs, rest


def _coarse(c):
    """A curve of a formula (exponential, sinc...) given as a short point list: at 3 or more points the slope changes in size,
    which straight-line shapes (pulses, triangles, steps) never do."""
    try: x, y = [float(v) for v in c['x']], [float(v) for v in c['y']]
    except (KeyError, TypeError, ValueError): return False
    if c.get('step') or c.get('stem') or c.get('markers') or not 4 <= len(x) <= 40 or len(x) != len(y): return False
    s = [(y[i + 1] - y[i]) / (x[i + 1] - x[i]) if x[i + 1] != x[i] else None for i in range(len(x) - 1)]
    bends = sum(1 for a, b in zip(s, s[1:]) if a and b and abs(abs(a) - abs(b)) > 0.1 * max(abs(a), abs(b)))
    return bends >= 3


def figure_problems(f, path, example_text=None):
    """A figure that cannot teach anything: data from another example, no axis labels, or a two-node diagram."""
    spec, kind, out = _dict(f.get('spec')), f.get('kind'), []
    if kind in ('plot', 'bars') and not (spec.get('xlabel') or spec.get('ylabel') or f.get('title') or spec.get('title') or f.get('caption')):
        out.append((path, f'the {kind} figure has no axis labels, title or caption: label what is plotted, with units', False))
    if kind == 'plot' and any(_coarse(c) for c in _list(spec.get('curves')) if isinstance(c, dict)):
        out.append((path, 'a smooth curve is given as a few points, so it is drawn as straight segments: give it as "expr" with "range"', False))
    if kind == 'graph' and len(_list(spec.get('nodes'))) < 3:
        out.append((path, 'a diagram of one or two nodes tells the student nothing: draw what the section needs (a plot, beam, circuit...) or leave it out', False))
    if example_text is not None:
        have = [abs(v) for v in _numbers(example_text) if v]
        data = [abs(v) for v in _numbers(spec) if abs(v) > 10 and v not in CONSTANTS]
        if len(data) >= 2 and not any(abs(v - h) <= 0.02 * h for v in data for h in have):
            out.append((path, 'the figure inside this worked example does not use any of the example\'s values: draw it from the example\'s own data', False))
    return out


def example_problems(b, path):
    """A numerical worked example (it has a "check") that is only a plug-in or whose working is a paragraph instead of
    steps. Conceptual examples reason in words and are not counted."""
    figs, rest = _figures_and_text([b.get('problem'), b.get('solution')] + [s.get('blocks') for s in b.get('steps') or [] if isinstance(s, dict)])
    sol = b.get('solution')
    worked = [s for s in b.get('steps') or [] if isinstance(s, dict) and (s.get('latex') or s.get('result'))]
    formulas = sum(1 for x in (sol if isinstance(sol, list) else []) if isinstance(x, dict) and x.get('type') in ('formula', 'table'))
    out = []
    if b.get('check') and len(worked) < 3 and formulas < 2 and json.dumps([sol, b.get('steps')], ensure_ascii=False).count('=') < 3:
        out.append((path, 'the worked example shows almost no working: make it a GATE 2-mark problem solved in 3 or more "steps" with the intermediate values', False))
    elif b.get('check') and not worked and formulas < 2:          # working written as paragraphs
        out.append((path, 'write the solution as "steps" (each with "say", one "latex" line of working and its "result"), not as paragraphs', False))
    return out + [p for f in figs for p in figure_problems(f, path, rest)]


META = re.compile(r'\b(schematic(ally)?|not (drawn )?to scale|drawn (at|as|in|with) |for (visual )?clarity|purely illustrative|for illustration)\b', re.I)


def writing_problems(note, path, earlier=()):
    """Plain, short writing (SME feedback: long, complicated paragraphs): sentences over 32 words, paragraphs over about 80 words, sections far over
    their word budget, sentences about how a figure is drawn, and key formulas repeated from an earlier section."""
    out, prose = [], 0
    for j, b in enumerate(note.get('blocks', [])):
        if not isinstance(b, dict): continue
        texts = [b.get('text', '')] if b.get('type') in ('para', 'note', 'callout', 'trap') else []
        texts += [b.get('caption', '')] if b.get('type') == 'figure' else []
        for t in texts:
            words = len(re.sub(r'\$[^$]*\$', 'x', str(t)).split())
            prose += words if b.get('type') == 'para' else 0
            longest = max((x for x in re.split(r'(?<=[.;:?!])\s+', re.sub(r'\$[^$]*\$', 'x', str(t)))), key=lambda x: len(x.split()), default='')
            if len(longest.split()) > 32:
                out.append((path + ('blocks', j), f'this sentence has {len(longest.split())} words ("{" ".join(longest.split()[:8])} ..."): '
                            'split it, one idea per sentence, conditions as bullets', False))
            if b.get('type') == 'para' and words > 85:
                out.append((path + ('blocks', j), f'this paragraph has {words} words: split it into short paragraphs (at most three sentences each) or bullets', False))
            if META.search(str(t)):
                out.append((path + ('blocks', j), 'remove the sentence about how the figure is drawn ("' + META.search(str(t)).group(0) + '"): the figure must show the idea itself', False))
        if b.get('type') == 'formula' and b.get('latex') and _key(b['latex']) in earlier:
            out.append((path + ('blocks', j), 'this formula repeats one from an earlier section: refer to it in words instead of teaching it again', False))
    if prose > 550:
        out.append((path, f'the section has about {prose} words of prose: cut it to about 400 (say each thing once; bullets for conditions)', False))
    return out


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
        earlier = {_key(b['latex']) for m in notes[:i] for b in m['blocks'] if isinstance(b, dict) and b.get('type') == 'formula' and b.get('key') and b.get('latex')}
        probs += [(item_path(p), m, h) for p, m, h in writing_problems(n, ('notes', i), earlier)]
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
    elif q.get('qtype') == 'MCQ' and re.fullmatch(r'[A-D]', str(q.get('answer', ''))) and 'ABCD'.index(q['answer']) < len(q.get('options') or []):
        opt = q['options']['ABCD'.index(q['answer'])]
        if re.search(r'[$/^\\]', opt): return out                  # 2.5 x 10^3, 1/3, $2^{10}$: not a plain number to compare
        try: number(opt)
        except ValueError: return out
        m = check_mismatch(q['check'], opt)
        return out + ([(path, m, False)] if m else [])
    else: return out
    return out + ([(path, m, 'cannot be evaluated' not in m)] if m else [])


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
    if out.get('case_study') and not out['case_study'].get('paragraphs'): probs.append((('case_study',), 'the case study needs "paragraphs"', True))
    return probs + drawing_problems(out)

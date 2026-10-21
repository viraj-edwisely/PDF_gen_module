"""Model replies of every odd shape: cleaning up and checking never raises, and the cases found by the edge-case review stay fixed.
Run with  python -m pytest tests"""
import copy, json, os, random, sys, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [APP, os.path.join(APP, 'render')]
import content as C
from safe_eval import safe_eval
G = json.load(open(os.path.join(APP, 'render', 'example_gate.json'), encoding='utf-8'))
N = json.load(open(os.path.join(APP, 'render', 'example_nongate.json'), encoding='utf-8'))


def test_edge_cases_from_the_review():
    def timed(expr):
        t = time.time()
        try: r = safe_eval(expr)
        except Exception as e: r = type(e).__name__
        assert time.time() - t < 1, expr
        return r
    assert timed('0x3000 - 0x1F4') == 11788 and timed('max(2, 3)') == 3 and timed('int(7.9)') == 7

    q = lambda **k: C.question(k)
    assert q(qtype='Multiple choice', options=['a', 'b', 'c', 'd'], answer='B')['qtype'] == 'MCQ'
    assert q(qtype='Multiple select', options=['a', 'b', 'c', 'd'], answer='A, C')['qtype'] == 'MSQ'
    assert q(qtype='MCQ', options=['a stack', 'b', 'c', 'd'], answer='a stack')['answer'] == 'A'
    assert q(qtype='MCQ', options=['x', 'y', 'z', 'w'], answer='2 A current')['answer'] == '2 A current'     # not silently "A"
    assert q(qtype='MCQ', options=['x', 'y', 'z', 'w'], answer='(b)')['answer'] == 'B'
    assert q(qtype='MCQ', options=['x', 'y', 'z', 'w'], answer='Option C')['answer'] == 'C'
    assert q(qtype='MSQ', options=['x', 'y', 'z', 'w'], answer='A and D')['answer'] == 'A, D'
    assert q(qtype='MCQ', options=['x', 'y', 'z', 'w'], answer='B) y')['answer'] == 'B'
    assert q(qtype='MCQ', options=['a', 'b', 'c', 'd', 'e'], answer='e')['answer'] == 'e'                  # F2: no IndexError
    for a, want in (('11,788', '11788'), ('1.5e-3', '0.0015'), ('2^10 = 1024', '1024'), ('.5', '0.5'), ('-2.25', '-2.25')):
        got = q(qtype='NAT', question='x ____', answer=a)['answer']; assert got == want, (a, got)
    assert q(qtype='NAT', question='x', answer='1500')['answer_range'] == '1500 to 1500'
    for opt, chk in (('$2.5 \\times 10^{3}$ N', '2500'), ('1/3', '1/3'), ('12 h', '12'), ('10 H', '10'), ('$2^{10}$ bytes', '1024')):
        probs = C.question_checks(C.question({'qtype': 'MCQ', 'question': 'q', 'options': [opt, 'b', 'c', 'd'], 'answer': 'A', 'check': chk}), ('practice', 0))
        assert not [p for p in probs if p[2]], (opt, probs)
    assert C.number('2E0CH') == 0x2E0C and C.number('0x2E0C') == 0x2E0C and C.number('12 h') == 12
    nat = C.question({'qtype': 'NAT', 'question': 'x ____', 'answer': '1024', 'check': '2^10'})
    assert not C.question_checks(nat, ('practice', 0)), C.question_checks(nat, ('practice', 0))
    bad = C.question({'qtype': 'NAT', 'question': 'x ____', 'answer': '3', 'check': 'log(1024, 2)'})
    assert all(not h for _, _, h in C.question_checks(bad, ('practice', 0)))
    assert C.figure_problems({'kind': 'plot', 'spec': {'xlabel': 'x', 'curves': 5}}, ()) == []
    for b in ({'type': 'note', 'text': 'x', 'solution': [{'type': 'figure', 'kind': ['plot']}]}, {'type': 'concept', 'text': 'x', 'problem': [{'type': {'a': 1}}]},
              {'type': 'trap', 'text': 'x', 'problem': ['a', {'type': 'para'}]}):
        t = C.blocks([b], 'nongate' if b['type'] == 'concept' else 'gate')
        assert C.block_problems(t, C.GATE_BLOCKS | C.NONGATE_BLOCKS, ()) == [], (b, t)
    assert C.item_path(()) == ()
    assert C.block({'type': 'figure', 'figure': {'type': 'plot', 'spec': {'curves': []}}}, 'gate')['type'] == 'figure'
    assert C.block({'type': 'figure', 'figure': {'type': 'plot', 'spec': {}}}, 'gate')['kind'] == 'plot'
    assert C.block({'type': 'figure', 'kind': 'Bar ', 'spec': {}}, 'gate')['kind'] == 'bars'
    assert C.block({'type': 'code', 'code': 'int x;'}, 'gate')['text'] == 'int x;'
    assert not C.raw_json({'type': 'code', 'text': '{"type": "A", "value": 3}'}) and not C.raw_json('Send `{"type": "A"}` to the API')
    assert C.block({'type': None, 'text': 'x'}, 'gate')['type'] == 'para'
    ng = C.block({'type': 'example', 'problem': ['Find x.', {'type': 'figure', 'kind': 'plot', 'spec': {'curves': [{'expr': 'x'}]}}], 'solution': ['x = 1']}, 'nongate')
    assert ng['type'] == 'worked_example' and ng['blocks'][1]['type'] == 'figure' and "{'curves'" not in ng['text'], ng
    assert C.clean('\\ud835\\udc65 x').encode('utf-8') and C.clean({'type': 'code', 'text': r'\(\d+\) \u0041'})['text'] == r'\(\d+\) \u0041'
    obj = {'notes': [{'blocks': [1, 2]}, {'blocks': [3, 4]}]}
    C.drop(obj, [('notes', 0), ('notes', 0, 'blocks', 0)]); assert obj == {'notes': [{'blocks': [3, 4]}]}, obj
    gq = C.gate_questions({'sample_paper': {'title': None, 'questions': []}})
    assert gq['sample_paper']['title'] == 'Sample paper (timed)'


NASTY = ['', ' ', 'x' * 3000, 'A' * 120, '$', '$$', 'cost $5 and $6', r'$\frac{1}{2', r'$\begin{array}{cc} 1 & 2 \\ 3 & 4 \end{array}$',
         '<b>bold</b> & <i>', '**unclosed bold', '`code', '50% & <5>', '\x00nul', 'back\\slash', r'\(x^2\)', r'\[x\]', '😀 हिंदी',
         'https://example.com/' + 'a' * 200, '1e999', '−5', 'NaN', '{"type": "para", "text": "json in string"}', r'$x_{1}^{2}$ and $\sqrt{}$',
         r'\\', '\n\n\n', 'Option (B)', 'A, B and D', '2 marks', 'None', r'$\left( x \right.$', r'$\mathbb{R}$', r'$a \over b$']


def nodes(x, path=()):
    yield path, x
    if isinstance(x, dict):
        for k, v in x.items(): yield from nodes(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from nodes(v, path + (i,))


def setp(root, path, v):
    cur = root
    for p in path[:-1]: cur = cur[p]
    cur[path[-1]] = v


def mutate(obj, rng, k):
    obj = copy.deepcopy(obj)
    for _ in range(k):
        ns = [(p, v) for p, v in nodes(obj) if p]
        if not ns: break
        path, v = rng.choice(ns)
        op = rng.randrange(12)
        parent = obj
        for p in path[:-1]: parent = parent[p]
        try:
            if op == 0 and isinstance(parent, dict): del parent[path[-1]]
            elif op == 1: setp(obj, path, None)
            elif op == 2: setp(obj, path, rng.choice(['', [], {}, 0, -1, 3.7, True]))
            elif op == 3: setp(obj, path, rng.choice(NASTY))
            elif op == 4 and isinstance(v, (int, float)) and not isinstance(v, bool): setp(obj, path, str(v) + rng.choice(['', ' marks', '.0', 'e3']))
            elif op == 5 and isinstance(v, str): setp(obj, path, [v, rng.choice(NASTY)])
            elif op == 6 and isinstance(v, list): setp(obj, path, {str(i): x for i, x in enumerate(v)})
            elif op == 7 and isinstance(v, (dict, list)): setp(obj, path, json.dumps(v))
            elif op == 8 and isinstance(v, list) and v: v.append(copy.deepcopy(rng.choice(v)))
            elif op == 9 and isinstance(v, list): v.clear()
            elif op == 10 and isinstance(parent, dict):
                alt = {'heading': 'title', 'title': 'heading', 'text': 'content', 'question': 'stem', 'options': 'choices', 'answer': 'correct',
                       'blocks': 'content', 'latex': 'formula', 'items': 'points', 'rows': 'data', 'spec': 'specification'}.get(path[-1], str(path[-1]) + 's')
                parent[alt] = parent.pop(path[-1])
            elif op == 11 and isinstance(v, str): setp(obj, path, v + ' ' + rng.choice(NASTY))
        except (KeyError, IndexError, TypeError):
            pass
    return obj


SECTIONS = [{'heading': n['heading'], 'figure': ''} for n in G['notes']]
REPLIES = {
    'gate_plan': ({'subtitle': G['subtitle'], 'syllabus_line': G['syllabus_line'], 'objectives': G['objectives'], 'prerequisites': G['prerequisites'],
                   'sections': [{'heading': n['heading'], 'ideas': 'x', 'example': 'y', 'figure': ''} for n in G['notes']], 'archetypes': ['a']},
                  C.gate_plan, C.gate_plan_problems),
    'gate_notes': ({'notes': G['notes']}, lambda x: C.align_notes(C.gate_notes(x), SECTIONS), lambda o: C.gate_notes_problems(o, SECTIONS)),
    'gate_questions': ({'practice': G['practice'], 'sample_paper': G['sample_paper'], 'traps': G['traps'], 'revision_card': G['revision_card']},
                       C.gate_questions, lambda o: C.gate_questions_problems(o, 'CS')),
    'pyq': ({'questions': G['pyqs']}, C.pyq_questions, lambda o: []),
    'gate_revision': ({'rows': [{'section': n['heading'], 'idea': 'one line', 'formula': 'x^2', 'rule': 'r', 'trap': 't'} for n in G['notes']], 'flow': ['A -> B']},
                      lambda x: C.gate_revision(x, G['notes']), lambda o: C.gate_revision_problems(o, G['notes'])),
    'structured_example': ({'notes': [{'heading': 'S', 'blocks': [{'type': 'formula', 'latex': 'F = ma', 'key': True, 'where': [['F', 'force', 'N']]},
                                                                  {'type': 'example', 'problem': 'p', 'given': [['m', '2 kg']], 'find': 'F',
                                                                   'steps': [{'say': 'Force', 'latex': 'F = 2 \times 3 = 6', 'result': '6 N'}], 'answer': '6 N', 'rushed': 'r'}]}]},
                           lambda x: C.align_notes(C.gate_notes(x), [{'heading': 'S', 'figure': ''}]), lambda o: C.gate_notes_problems(o, [{'heading': 'S', 'figure': ''}])),
    'nongate_plan': ({'title': N['title'], 'description': N['description'], 'topics': [{'title': t['title'], 'tagline': t['tagline']} for t in N['topics']], 'case_study': True},
                     C.nongate_plan, C.nongate_plan_problems),
    'nongate_topics': ({'topics': [{'blocks': t['blocks']} for t in N['topics']]}, C.nongate_topics, lambda o: C.nongate_topics_problems(o, len(N['topics']))),
    'nongate_end': ({'case_study': N['case_study'], 'practice': N['practice'], 'revision': N['revision']}, C.nongate_end, C.nongate_end_problems),
}


def test_fuzzed_replies_never_raise(monkeypatch):
    monkeypatch.setattr(C, 'drawing_problems', lambda out: [])      # the drawing subprocess is covered by test_render
    rng = random.Random(7)
    for _ in range(1500):
        name = rng.choice(list(REPLIES))
        base, tidy, problems = REPLIES[name]
        reply = mutate(base, rng, rng.randint(1, 6)) if rng.random() < 0.95 else rng.choice([[], 'text', None, 5, {'x': 1}])
        out = tidy(reply)
        probs = problems(out)
        if [m for p, m, h in probs if not p and h]: continue
        C.drop(out, [p for p, m, h in probs if h and len(p) > 1])
        problems(out)

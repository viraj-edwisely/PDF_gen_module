"""Offline checks of the content rules (no database, no model): run with  python -m pytest tests"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import content as C


def test_blocks_are_tidied():
    bs = C.blocks(['plain', {'type': 'paragraph', 'content': 'x'}, {'type': 'list', 'points': ['a', {'text': 'b'}]},
                   {'type': 'equation', 'latex': '$$x^2$$'}, {'type': 'image', 'path': 'nowhere.png'},
                   {'type': 'worked_example', 'question': 'Q?', 'answer': 'A.'}, {'type': 'table', 'rows': [{'a': 1, 'b': 2}]}], 'gate')
    assert [b['type'] for b in bs] == ['para', 'para', 'bullets', 'formula', 'example', 'table']
    assert bs[1]['text'] == 'x' and bs[2]['items'] == ['a', 'b'] and bs[3]['latex'] == 'x^2'
    assert bs[4]['problem'] == 'Q?' and bs[4]['steps'] == [{'text': 'A.'}]          # a solution paragraph becomes a step
    assert bs[5]['header'] == ['a', 'b'] and bs[5]['rows'] == [['1', '2']]


def test_solutions_become_steps_and_symbol_tables_become_where_lists():
    """SME feedback: solutions written as paragraphs, and Symbol / Meaning / Unit tables after every formula."""
    ex = C.block({'type': 'example', 'problem': 'p', 'solution': {'given': ['m = 20 kg'], 'steps': [
        {'label': 'Kinetic energy', 'formula': r'$\Delta KE = 2.0\ \mathrm{kJ}$'}, '2. Then the potential energy.'], 'answer': 35.6}}, 'gate')
    assert ex['steps'] == [{'say': 'Kinetic energy', 'latex': r'\Delta KE = 2.0\ \mathrm{kJ}'}, {'text': 'Then the potential energy.'}]
    assert ex['given'] == ['m = 20 kg'] and ex['answer'] == '35.6' and 'solution' not in ex
    assert C._steps('First find A.\n\n1. Then B.\n2. Then C.') == [{'text': 'First find A.'}, {'text': 'Then B.'}, {'text': 'Then C.'}]
    bs = C.blocks([{'type': 'formula', 'latex': r'F = \rho g V'},
                   {'type': 'table', 'header': ['Symbol', 'Meaning', 'SI unit'], 'rows': [[r'$\rho$', 'density', 'kg/m$^3$'], ['g', 'gravity', 'm/s$^2$']]}], 'gate')
    assert len(bs) == 1 and bs[0]['where'] == [[r'$\rho$', 'density', 'kg/m$^3$'], ['g', 'gravity', 'm/s$^2$']]
    assert C._where({'V': 'volume'}) == [['V', 'volume']] and C._where(['ρ = density of the fluid (kg/m³)']) == [['ρ', 'density of the fluid', 'kg/m³']]


def test_questions_are_tidied():
    q = C.question({'type': 'mcq', 'stem': 'Which?', 'options': {'A': '(A) one', 'B': 'B. two', 'C': 'three', 'D': 'four'}, 'answer': '(B)', 'marks': '1 mark'})
    assert q['qtype'] == 'MCQ' and q['question'] == 'Which?' and q['options'][:2] == ['one', 'two'] and q['answer'] == 'B' and q['marks'] == 1
    n = C.question({'qtype': 'Numerical', 'question': 'x ______', 'answer': '1.20 s', 'marks': 2})
    assert n['qtype'] == 'NAT' and n['answer'] == '1.20' and n['answer_range'] == '1.19 to 1.21'
    m = C.question({'qtype': 'MSQ', 'question': 'q', 'options': ['a', 'b', 'c', 'd'], 'answer': 'A and C'})
    assert m['answer'] == 'A, C'


def test_practice_levels_and_sample_marks_are_fixed_in_code():
    out = C.gate_questions({'practice': [{'level': 'hard', 'question': 'h'}, {'level': 'easy', 'question': 'e'}, {'question': 'm'}],
                            'sample_paper': [{'marks': 1, 'question': 's1'}, {'marks': 2, 'question': 's2'}], 'traps': [{'title': 'T', 'text': 'x'}]})
    assert [q['level'] for q in out['practice']] == ['Easy', 'Hard', 'Hard']
    assert out['sample_paper']['marks'] == 3 and out['traps'] == ['**T:** x']


def test_nul_and_target_year_are_removed():
    assert C.clean({'a': 'x\x00y GATE 2027 prep', 'source': 'CS-GATE-2019'}) == {'a': 'xy GATE prep', 'source': 'CS-GATE-2019'}


def test_answer_checks_catch_arithmetic_slips():
    assert C.check_mismatch({'expr': '0x3000 - 0x1F4', 'answer': '0x2E0C'}) is None
    assert 'gives 11788' in C.check_mismatch({'expr': '0x3000 - 0x1F4', 'answer': '2E14_H'})
    assert C.check_mismatch('0.40*ceil(1.05/0.40)', '1.2', '1.19 to 1.21') is None
    assert 'outside' in C.check_mismatch('3050 + 20 - 30', '3050', '3049 to 3051')
    assert 'cannot be evaluated' in C.check_mismatch('__import__("os")', '1')


def test_maths_problems():
    probs = C.math_problems({'text': 'EA = 4416_{10}$'}, ('notes', 0, 'blocks', 2))
    assert probs and probs[0][1].startswith('unbalanced $')
    assert C.math_problems({'type': 'code', 'text': 'echo $HOME'}, ()) == []
    assert C.math_problems({'text': r'$\begin{cases} a & x > 0 \end{cases}$', 'latex': r'\boxed{x} \xrightarrow{f} y'}, ()) == []    # rewritten by render/tex.py
    assert 'cannot be drawn' in C.math_problems({'text': r'$\begin{tikzpicture} a \end{tikz}$'}, ())[0][1]                 # an environment it cannot rewrite


def test_paths():
    assert C.item_path(['notes', 1, 'blocks', 3, 'problem', 0, 'text']) == ('notes', 1, 'blocks', 3)
    assert C.item_path(['sample_paper', 'questions', 2, 'solution']) == ('sample_paper', 'questions', 2)
    assert C.item_path(['notes', 1, 'heading']) == ('notes', 1)
    obj = {'practice': [0, 1, 2, 3], 'notes': [{'blocks': ['a', 'b', 'c']}]}
    C.drop(obj, [('practice', 1), ('practice', 3), ('notes', 0, 'blocks', 0)])
    assert obj == {'practice': [0, 2], 'notes': [{'blocks': ['b', 'c']}]}
    C.put(obj, C.unref('notes/0/blocks/1'), 'z'); C.put(obj, ('traps',), ['t'])
    assert obj['notes'][0]['blocks'] == ['b', 'z'] and obj['traps'] == ['t']


def test_question_checks_feed_problems():
    q = C.question({'qtype': 'NAT', 'question': 'EA ______', 'answer': '3040', 'check': '3050 + 20 + 30', 'marks': 2, 'solution': 's'})
    assert C.question_checks(q, ('practice', 0))[0][0] == ('practice', 0)


def test_failures_seen_in_real_pdfs():
    """Cases from the Torsion and Fourier PDFs (2026-10-16)."""
    import llm
    # LaTeX with one backslash: \frac must not become a form feed, \right not a carriage return
    o = llm.parse_json(r'{"a": "$\frac{1}{2}$ \right) \theta", "b": "one\nTwo"}')
    assert o == {'a': r'$\frac{1}{2}$ \right) \theta', 'b': 'one\nTwo'}
    # LaTeX symbols that are not JSON escapes (Graphs PDF): \{ \, \% \_ \; \! \| \( and digits
    o = llm.parse_json(r'{"a": "$V = \{1, 2\}$, $a\,b\;c\!d$, 50\% of x\_1, \|E\|, \(x\) \\ \2", "b": "line\nnext \"q\" \/ ½"}')
    assert o == {'a': r'$V = \{1, 2\}$, $a\,b\;c\!d$, 50\% of x\_1, \|E\|, \(x\) \ \2', 'b': 'line\nnext "q" / ½'}
    assert llm.parse_json('{"a": "two\nlines"}') == {'a': 'two\nlines'}       # a raw line break inside a string
    assert C.clean(r'degree \(d(v) = 3\) and \[ \sum d = 2|E| \], rows a \\[2pt] b') == r'degree $d(v) = 3$ and $\sum d = 2|E|$, rows a \\[2pt] b'
    # a block written as a string of JSON becomes a block; leaked JSON in text is a hard problem
    assert C.block('{"type": "formula", "latex": "x = 1"}', 'gate') == {'type': 'formula', 'latex': 'x = 1'}
    leak = [{'type': 'para', 'text': 'ref":"notes/1","value":{' + '}]' * 10}]
    assert C.block_problems(leak, C.GATE_BLOCKS, ('notes', 0, 'blocks'))[0][2] is True
    # data used by the check but missing from the question (G = 80 GPa); exponents are not data
    q = {'qtype': 'NAT', 'question': 'Shaft: 90 kW at 300 rpm, twist 1.5 deg over 2 m. D in mm is ______', 'answer': '76.8',
         'check': '1000*(32*2865*2/(3.14159*80e9*0.02618*0.8025))**0.25'}
    assert 'uses 80e9' in C.question_checks(C.question(q), ('practice', 0))[0][1]
    q['question'] = q['question'].replace('2 m.', '2 m, G = 80 GPa.')
    assert not [m for _, m, _ in C.question_checks(C.question(q), ('practice', 0)) if 'does not state' in m]
    # NAT ranges accept the usual approximations; written-out escapes become characters
    assert C.question({'qtype': 'NAT', 'question': 'x ______', 'answer': '382.0', 'answer_range': '381.99 to 382.01'})['answer_range'] == '381.6 to 382.4'
    assert C.clean(r'\u00bdS(j\u03c9) \u0024') == '½S(jω) $'
    # an MSQ whose options are letter combinations is malformed
    msq = {'qtype': 'MSQ', 'question': 'A. x B. y', 'options': ['A, B, C', 'A, C, D', 'B, C, D', 'A, B, D'], 'answer': 'A'}
    assert C.question_checks(C.question(msq), ('practice', 2))
    assert llm.stuck('{"a": 1' + '}]' * 2000) and not llm.stuck('ordinary words ' * 40)


def test_notes_are_matched_to_the_plan():
    """A reply with sections missing, renamed or reordered is not thrown away: the missing one goes to the repair."""
    plan = [{'heading': h} for h in ('Definition of the Fourier transform', 'Properties', 'Common pairs', 'Parseval')]
    ex = {'type': 'example', 'problem': 'p', 'solution': 's'}
    reply = {'notes': [{'heading': 'Common Fourier pairs', 'blocks': ['c', ex]}, {'heading': 'Definition of the Fourier Transform', 'blocks': ['d', ex]},
                       {'heading': 'Properties', 'blocks': ['p', ex]}]}
    out = C.align_notes(C.gate_notes(reply), plan)
    assert [n['heading'] for n in out['notes']] == [p['heading'] for p in plan]
    assert [n['blocks'][0]['text'] for n in out['notes'][:3]] == ['d', 'p', 'c'] and out['notes'][3]['blocks'] == []
    probs = [p for p in C.gate_notes_problems(out, plan) if p[0] == ('notes', 3)]
    assert probs and probs[0][2] and 'Parseval' in probs[0][1]
    same = C.align_notes(C.gate_notes({'notes': [{'blocks': ['x']}] * 4}), plan)        # no headings, right count: by position
    assert all(n['blocks'] for n in same['notes'])
    assert C.gate_notes_problems(C.align_notes(C.gate_notes({}), plan), plan)[0][0] == ()   # nothing usable: ask again


def test_name_sake_content_is_flagged():
    """Worked examples and figures that exist only to tick a box (seen in the Torsion and Fourier PDFs)."""
    fig = {'type': 'figure', 'kind': 'plot', 'spec': {'xlabel': 'θ', 'ylabel': 'T', 'curves': [{'expr': '4774.6 + 1432.4*sin(x)', 'range': [0, 6.3]}]}}
    ex = {'type': 'example', 'problem': ['60 kW at 240 rpm, Tmax 25% above the mean.', fig],
          'solution': [{'type': 'formula', 'latex': 'T = 2387.3'}, {'type': 'formula', 'latex': 'T_{max} = 2984.2'}], 'check': '2387.3*1.25'}
    assert any('does not use any of the example' in m for _, m, _ in C.example_problems(ex, ('notes', 0, 'blocks', 1)))
    fig['spec']['curves'][0]['expr'] = '2387.3 + 596.9*sin(x)'
    assert C.example_problems(ex, ('notes', 0, 'blocks', 1)) == []
    assert C.example_problems({'type': 'example', 'problem': 'Find X(j0).', 'solution': 'X(j0) = 2T1.', 'check': '0.004'}, ())
    assert C.example_problems({'type': 'example', 'problem': 'What happens?', 'solution': 'P1 pre-empts P3.'}, ()) == []   # conceptual
    assert C.figure_problems({'kind': 'graph', 'spec': {'nodes': ['a', 'b']}}, ())
    assert C.figure_problems({'kind': 'plot', 'spec': {'curves': []}}, ())
    exp = {'x': [0, 1, 2, 3, 4, 5], 'y': [1, 0.135, 0.018, 0.002, 0.0003, 0]}          # e^{-2t} as six points: jagged
    assert any('expr' in m for _, m, _ in C.figure_problems({'kind': 'plot', 'spec': {'xlabel': 't', 'curves': [exp]}}, ()))
    for shape in ({'x': [-2, -1, -1, 1, 1, 2], 'y': [0, 0, 1, 1, 0, 0]}, {'x': [0, 1, 2, 3, 4, 5, 6], 'y': [0, 1, 0, 1, 0, 1, 0]}):   # pulse, triangle wave
        assert not C.figure_problems({'kind': 'plot', 'spec': {'xlabel': 't', 'curves': [shape]}}, ())


def test_parse_json_escapes_and_wrapping():
    """Audit cases: \\uXXXX escapes, LaTeX commands that start like JSON escapes, prose with braces, NUL, lists."""
    import llm
    assert llm.parse_json(r'{"a": "90° → 𝑥 ꯍ"}') == {'a': '90° → 𝑥 ꯍ'}
    for cmd in ('boxed{5}', 'bigcup', 'bmod', 'because', 'bot', 'fbox{x}', 'textit{x}', 'texttt{x}', 'therefore', 'triangleq', 'tag{1}',
                'nleq', 'ngeq', 'nexists', 'newline', 'rvert', 'rbrace', 'rightleftharpoons', 'notin', 'underline{x}', 'frac{1}{2}'):
        assert llm.parse_json('{"a": "$\\' + cmd + '$"}') == {'a': '$\\' + cmd + '$'}, cmd
    assert llm.parse_json(r'{"a": "one\nThe\ni.e. x\ni) y\ne) z\t1", "b": "$\ni$ $\ne 1$"}') == {'a': 'one\nThe\ni.e. x\ni) y\ne) z\t1', 'b': r'$\ni$ $\ne 1$'}
    assert llm.parse_json('Using format {x}: {"a": 1} Let me know if {you} need more') == {'a': 1}
    assert llm.parse_json('[{"a": 1}]') == {'a': 1}
    assert llm.parse_json(r'{"a": "x\\u0000", "b": "y\u0000z"}') == {'a': r'x\u0000', 'b': 'yz'}
    assert not llm.stuck('[' + '0,' * 1400)


def test_plan_must_teach_every_subtopic_and_explain_missing_figures():
    plan = C.gate_plan({'objectives': ['x'], 'sections': [{'heading': 'Buoyant force', 'figure': 'geometry: ...'}, {'heading': 'Metacentre', 'figure': ''},
                                                          {'heading': 'Experimental GM', 'figure': '', 'no_figure_reason': 'a table says it all'}],
                        'coverage': [{'subtopic': 'Archimedes principle', 'section': 'Buoyant force'}]})
    probs = C.gate_plan_problems(plan, ['Archimedes principle', 'Metacentric height', 'Stability of floating bodies'])
    msgs = ' '.join(m for _, m, _ in probs)
    assert 'Stability of floating bodies' in msgs and 'Archimedes' not in msgs          # covered by name, missing reported
    assert any(p == ('sections', 1) for p, _, _ in probs) and not any(p == ('sections', 2) for p, _, _ in probs)


def test_long_paragraphs_figure_apologies_and_repeated_formulas_are_flagged():
    note = {'heading': 'S', 'blocks': [{'type': 'para', 'text': 'word ' * 90},
                                       {'type': 'figure', 'kind': 'plot', 'spec': {}, 'caption': 'The cross-section is schematic; parts are drawn at separate positions.'},
                                       {'type': 'formula', 'latex': 'F_B = \rho g V', 'key': True}]}
    msgs = [m for _, m, _ in C.writing_problems(note, ('notes', 1), {C._key('F_B = \rho g V')})]
    assert any('90 words' in m for m in msgs) and any('schematic' in m for m in msgs) and any('repeats' in m for m in msgs)
    assert C.writing_problems({'heading': 'S', 'blocks': ['Short and plain.']}, ('notes', 0)) == []

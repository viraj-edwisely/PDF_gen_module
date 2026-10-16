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
    assert bs[4]['problem'] == 'Q?' and bs[4]['solution'] == 'A.'
    assert bs[5]['header'] == ['a', 'b'] and bs[5]['rows'] == [['1', '2']]


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
    assert 'cannot be drawn' in C.math_problems({'text': r'$\begin{cases} a \end{cases}$'}, ())[0][1]


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

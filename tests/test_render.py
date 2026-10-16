"""The renderers never fail because of content: broken parts are left out and reported. Run with  python -m pytest tests"""
import json, os, subprocess, sys, tempfile
RENDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'render')


def render(mode, content):
    d = tempfile.mkdtemp(); src, pdf = os.path.join(d, 'c.json'), os.path.join(d, 'o.pdf')
    json.dump(content, open(src, 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, os.path.join(RENDER, f'render_{mode}.py'), src, pdf], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stderr[-500:]
    assert os.path.getsize(pdf) > 10_000
    return json.loads(r.stdout.strip().splitlines()[-1])['warnings']


def test_gate_with_broken_parts_still_renders():
    c = json.load(open(os.path.join(RENDER, 'example_gate.json'), encoding='utf-8'))
    c['notes'][0]['blocks'] += [
        {'type': 'image', 'path': 'figures/nowhere.png'},                                   # invented file (crashed the old renderer)
        {'type': 'figure', 'kind': 'plot', 'spec': {'curves': [{'expr': 'import os'}]}},     # a figure that cannot be drawn
        {'type': 'para', 'content': 'renamed field'},                                        # KeyError: 'text' before
        {'type': 'table', 'header': ['a', 'b'], 'rows': [['1'], ['2', '3', '4']]},           # ragged rows
        {'type': 'para', 'text': r'$Operand = \begin{cases} a & b \end{cases}$ and EA = 4416_{10}$'},
        {'type': 'example', 'title': 'Example: Worked example: x', 'problem': 'p', 'solution': [{'type': 'mystery'}]}]
    c['practice'][0] = {'qtype': 'MCQ', 'options': [1, 2, 3, 4]}                                # no question, no marks, no answer
    c['practice'][1]['figure'] = {'kind': 'graph', 'spec': {'edges': 'oops'}}
    warnings = render('gate', c)
    assert any('could not be drawn' in w for w in warnings)


def test_nongate_with_missing_fields_still_renders():
    c = json.load(open(os.path.join(RENDER, 'example_nongate.json'), encoding='utf-8'))
    c['topics'][0]['blocks'] += [{'type': 'quick_check'}, {'type': 'situation'}, {'type': 'worked_example', 'text': 'x', 'blocks': [{'type': 'figure', 'kind': 'nope'}]}]
    c['case_study'] = {'title': 'CS'}                                                         # no paragraphs
    c['practice'] = [{'question': 'q only'}]
    c['revision'] = {'concepts': [{'title': 't'}], 'distinctions': {'header': ['a']}, 'mistakes': [{}], 'checklist': ['x']}
    render('nongate', c)

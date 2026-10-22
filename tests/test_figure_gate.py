"""Figures that draw but are muddled are caught and left out of the PDF: python -m pytest tests"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), 'render')]
import check_content, figures, review

# a distillation column drawn as a signal chain (what the writer did): the labels collide and the arrows are not streams
COLUMN = {'chain': [{'el': 'in', 'label': 'Feed F'}, {'el': 'box', 'label': 'Staged column', 'id': 'col'}, {'el': 'box', 'label': 'Condenser', 'id': 'cond'},
                    {'el': 'out', 'label': 'Distillate D'}],
          'side': [{'el': 'box', 'label': 'Reboiler', 'into': 'col', 'from': 'bottom', 'edge': 'boilup'}],
          'feedback': [{'from': 'cond', 'to': 'col', 'box': 'Reflux', 'sign': '+'}]}
LOOP = {'chain': [{'el': 'in', 'label': 'R(s)'}, {'el': 'sum', 'id': 's', 'label': ''}, {'el': 'box', 'label': 'G(s)', 'id': 'g'}, {'el': 'out', 'label': 'C(s)'}],
        'feedback': [{'from': 'g', 'to': 's', 'box': 'H(s)', 'sign': '−'}], 'signs': {'s': {'W': '+'}}}


class Job:
    def __init__(self): self.warnings = []
    def warn(self, text): self.warnings.append(text)


def test_block_diagram_reports_labels_that_collide():
    assert figures.overlaps(figures.render('block', COLUMN)) > 0
    assert figures.overlaps(figures.render('block', LOOP)) == 0          # a normal feedback loop is clean


def test_block_diagram_is_not_for_process_equipment():
    assert 'process kind' in check_content.misuse('block', COLUMN)
    assert check_content.misuse('block', LOOP) == ''


def test_figure_still_wrong_is_left_out_but_a_question_keeps_its_figure():
    fig = {'type': 'figure', 'kind': 'block', 'spec': COLUMN}
    content = {'notes': [{'heading': 'Column', 'blocks': ['text', fig, 'more text']}],
               'practice': [{'question': 'In the figure, find D.', 'figure': {'kind': 'block', 'spec': COLUMN}}]}
    job = Job()
    review.leave_out(job, content, [(('notes', 0, 'blocks', 1), 'labels overlap'), (('practice', 0, 'figure'), 'labels overlap')])
    assert content['notes'][0]['blocks'] == ['text', 'more text']
    assert content['practice'][0]['figure']['kind'] == 'block'
    assert len(job.warnings) == 2 and 'left out' in job.warnings[0] and 'Please check' in job.warnings[1]

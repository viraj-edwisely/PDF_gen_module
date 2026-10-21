"""Page layout: boxes split only where they may, tables keep words whole, topics keep their subtopics out of the title,
and the finished PDF is read back for leaks and empty pages. python -m pytest tests"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), 'render')]
import render_common as R
import content as C
from reportlab.platypus import Paragraph


def test_a_box_title_never_ends_a_page_alone():
    title = R.keep(Paragraph('Common GATE trap', R.S['boxtitle']))
    body = [R.P('A long explanation. ' * 40) for _ in range(3)]
    b = R.box([R.P('Intro line.'), title] + body)
    b.wrap(R.TW, 1000)
    room = 2 * b.pad + b.sizes[0][1] + b.sizes[1][1] + 6          # just room for the intro and the title
    parts = b.split(R.TW, room)
    assert parts and parts[0].flows[-1] is not title                # the title moved on with its text
    assert R.box([title] + body).split(R.TW, 40) == []              # nothing useful fits: the whole box moves, no empty strip


def test_table_columns_hold_their_longest_word():
    header = ['Scheme', 'Bits/symbol', 'Signal-space dimension and geometry', 'Detection and error reference', 'Bandwidth and efficiency notes', 'Main trade-off']
    rows = [['Binary ASK/OOK', '1', 'One-dimensional amplitude levels', 'Coherent threshold detection', 'Raised-cosine estimate', 'Constant-envelope signalling']]
    cols = [[h] + [r[j] for r in rows] for j, h in enumerate(header)]
    widths, size = R.column_widths(cols, R.TW)
    assert abs(sum(widths) - R.TW) < 1 and size >= 7
    for col, w in zip(cols, widths):
        longest = max(R.pdfmetrics.stringWidth(word, 'BodyB', size) for c in col for word in c.split())
        assert longest + 12 <= w + 0.5, (col[0], longest, w)


def test_subtopics_are_split_from_the_title():
    assert C.split_topic('Buoyancy and Metacentric Height (Buoyant Force, Centre of Buoyancy, Metacentre)') == \
        ('Buoyancy and Metacentric Height', ['Buoyant Force', 'Centre of Buoyancy', 'Metacentre'])
    assert C.split_topic("Kirchhoff's laws (KCL)") == ("Kirchhoff's laws (KCL)", [])
    assert C.split_topic('Rankine cycle', 'Reheat; Regeneration') == ('Rankine cycle', ['Reheat', 'Regeneration'])


def test_leaks_in_the_finished_text_are_found():
    leak = R.LEAK.search
    assert leak(r'I = 20.48 \times 10^6') and leak('mm^4') and leak('"type": "para"') and leak('Answer: None')
    assert not leak('(D) None of these') and not leak('10⁶ mm⁴ and kg/m³')

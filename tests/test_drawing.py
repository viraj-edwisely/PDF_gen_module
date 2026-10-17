"""Every formula style and every figure kind draws, and the drawings fit the page: python -m pytest tests
(graph figures need Graphviz; they are skipped where it is not installed)."""
import os, shutil, sys
import pytest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), 'render')]
import figures, render_common as R, tex as TEX
from stress_data import AWKWARD, FORMULAS
from PIL import Image

HAS_DOT = bool(shutil.which('dot'))


def test_every_formula_draws_as_display_and_inline():
    for t in FORMULAS:
        for line in TEX.lines(t): R.math_img(line, 11, True)
        R.math_img(t, 10.5, False)


def test_inline_maths_keeps_the_line_height():
    _, _, h = R.math_img(r'x_p(t) = \sum_{n=-\infty}^{\infty} \delta(t - nT)', 10.5, False)
    assert h < 22                     # limits beside the sign, not stacked (stacked is about 30 pt)


@pytest.mark.parametrize('name', list(figures.GALLERY))
def test_gallery_figures_draw(name):
    kind, spec = figures.GALLERY[name]
    if kind == 'graph' and not HAS_DOT: pytest.skip('Graphviz not installed')
    figures.render(kind, spec)


@pytest.mark.parametrize('title,kind,spec', AWKWARD, ids=[a[0][:40] for a in AWKWARD])
def test_awkward_figures_draw_and_fit(title, kind, spec):
    if kind == 'graph' and not HAS_DOT: pytest.skip('Graphviz not installed')
    im = Image.open(figures.render(kind, spec))
    w_in = im.size[0] / (im.info.get('dpi') or (figures.DPI,))[0]
    assert w_in < 8.5, f'{title}: {w_in:.1f} in wide, the PDF would shrink its text'


def test_circuit_anchors_are_positions_in_the_drawing():
    import schemdraw, schemdraw.elements as E
    with schemdraw.Drawing(show=False) as d:
        r = E.Resistor().right(); d += r
        n = E.Dot(); d += n
        assert tuple(figures._anchor({'n': n}, 'n.center')) == tuple(r.end) != (0, 0)


def test_labels_written_as_latex_read_as_text():
    assert figures.text_label(r'X(j\omega)') == 'X(jω)' and figures.text_label('{1,2}') == '{1,2}'

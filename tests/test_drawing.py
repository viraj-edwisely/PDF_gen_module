"""Every formula style and every figure kind draws, and the drawings fit the page: python -m pytest tests
(graph figures need Graphviz; they are skipped where it is not installed)."""
import os, shutil, sys
import pytest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), 'render')]
import figures, render_common as R, tex as TEX
from stress_data import AWKWARD, FORMULAS
from sme_figures import SME_FIGURES, TOO_FAST
from PIL import Image

HAS_DOT = bool(shutil.which('dot'))


def test_every_formula_draws_as_display_and_inline():
    for t in FORMULAS:
        for line in TEX.lines(t): R.math_img(line, 11, True)
        R.math_img(t, 10.5, False)


def test_inline_maths_keeps_the_line_height():
    _, _, h, _ = R.math_img(r'x_p(t) = \sum_{n=-\infty}^{\infty} \delta(t - nT)', 10.5, False)
    assert h < 26                     # limits beside the sign, not stacked (stacked is about 34 pt); 4 pt of it is padding


def test_inline_superscript_sits_above_the_baseline():
    """mm$^2$ printed as mm₂ (ME PDFs): the image was cropped to its ink, losing where the baseline was."""
    _, _, h, d = R.math_img('^2', 10.5, False)
    _, _, hx, dx = R.math_img('x', 10.5, False)
    assert d == dx == R.MATH_PAD and h >= hx            # same baseline as a plain letter, raised digit inside the box


def test_units_and_powers_outside_maths_print_as_characters():
    """Seen in the reviewed PDFs: mm$^2$, 10^6 mm^4, kg/m3, N.m, and \\\\text over-escaped in JSON ("d; textmin")."""
    assert TEX.plain('A = 9600 mm$^2$; I = 20.48 × 10^6 mm^4.') == 'A = 9600 mm²; I = 20.48 × 10⁶ mm⁴.'
    assert TEX.plain('ρ in kg/m3, g in m/s2, M in kN.m') == 'ρ in kg/m³, g in m/s², M in kN·m'
    assert TEX.plain('masses m1 and m2') == 'masses m1 and m2'            # variables keep their digits
    assert TEX.plain('$x^2$ and **bold**') == '$x^2$ and **bold**'
    assert TEX.normalize('d_{' + '\\\\' + 'text{min}}') == r'd_{\mathrm{min}}'
    assert TEX.normalize('10^-3 + e^-j\\omega') == r'10^{-3} + e^{-j\omega}'
    assert TEX.display(r'\frac{a}{b} + x^{\frac{1}{2}}') == r'\dfrac{a}{b} + x^{\frac{1}{2}}'    # full size, except inside a power


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


LOOP = {'a': [0, 2], 'b': [3, 2], 'g': [0, 0], 'h': [3, 0]}          # a source and a resistor joined by a wire at the bottom
BROKEN_CIRCUITS = [        # (what a writer got wrong, nodes, parts, a phrase the message must contain): each was drawn silently before
    ('a part left open', dict(LOOP, c=[6, 2]), [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'b'], ['R2', 'R', 'b', 'h'], ['', 'W', 'g', 'h'], ['R4', 'R', 'b', 'c']], 'left open'),
    ('a galvanometer shorted by the rail', LOOP, [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'b'], ['R2', 'R', 'b', 'h'], ['', 'W', 'g', 'h'], ['G', 'R', 'g', 'h']], 'shorted'),
    ('a part over a node', dict(LOOP, c=[6, 2], k=[6, 0]), [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'c'], ['R2', 'R', 'b', 'h'], ['', 'W', 'g', 'h'], ['', 'W', 'h', 'k'], ['R3', 'R', 'c', 'k']], 'runs over node'),
    ('every grounded part on one node (SPICE)', {'a': [0, 2], 'n': [3, 2], 'g': [0, 0]}, [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'n'], ['R2', 'R', 'n', 'g']],
     r"new node at \[3, 0\] and join that node to 'g'"),
    ('parallel parts on the same nodes (SPICE)', LOOP, [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'b'], ['R2', 'R', 'b', 'h'], ['G', 'Idep', 'b', 'h'], ['', 'W', 'g', 'h']],
     r'draw G beside R2, between new nodes at \[5, 2\] and \[5, 0\]'),
    ('lines crossing', dict(LOOP, c=[1.5, 3], d=[1.5, 1]), [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'b'], ['R2', 'R', 'b', 'h'], ['', 'W', 'g', 'h'], ['R3', 'R', 'c', 'd']], 'crosses'),
    ('a wire through the op-amp', {'s': [0, 2.5], 'g': [0, 1], 'k': [3, 1]},
     [['V', 'V', 's', 'g'], ['R1', 'R', 's', 'm'], ['U1', 'opamp', 'm', 'p', 'o', '', {'at': [4, 2]}], ['', 'W', 'p', 'k'], ['', 'W', 'g', 'k'], ['RL', 'R', 'o', 'm']], 'symbol of U1'),
    ('a pin node given another place', dict(LOOP, m=[2, 2]), [['V1', 'V', 'a', 'g'], ['U1', 'opamp', 'm', 'g', 'b', '', {'at': [4, 2]}]], 'leave pin nodes out'),
]


@pytest.mark.parametrize('what,nodes,parts,says', BROKEN_CIRCUITS, ids=[b[0] for b in BROKEN_CIRCUITS])
def test_circuit_refuses_what_a_textbook_never_prints(what, nodes, parts, says):
    with pytest.raises(ValueError, match=says):
        figures.render('circuit', {'nodes': nodes, 'parts': parts})


def test_circuit_wire_over_nodes_joins_them_and_repeats_are_drawn_once():
    """A return rail written as one wire under the parts' nodes, plus the same wire again: what the picture shows is meant."""
    spec = {'nodes': dict(LOOP, c=[6, 2], k=[6, 0]), 'parts': [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'b'], ['R2', 'R', 'b', 'h'], ['', 'W', 'b', 'c'],
                                                              ['Z1', 'Z', 'c', 'k', 'Z_L'], ['', 'W', 'g', 'k'], ['', 'W', 'k', 'g']]}
    import fig_circuit
    assert fig_circuit.check(spec) == [] and figures.overlaps(figures.render('circuit', spec)) == 0


def test_circuit_ground_under_every_branch_becomes_one_rail():
    """Seen in a live run: a ground symbol under each of four branches. Textbooks draw one return rail and one ground."""
    import fig_circuit
    spec = {'nodes': {'t1': [0, 3], 't2': [3, 3], 't3': [6, 3], 'g1': [0, 0], 'g2': [3, 0], 'g3': [6, 0]}, 'ground': ['g1', 'g2', 'g3'],
            'parts': [['V1', 'V', 't1', 'g1'], ['R2', 'R', 't2', 'g2'], ['R3', 'R', 't3', 'g3'], ['', 'W', 't1', 't3']]}
    nodes, parts, _, _, ground = fig_circuit._layout(spec, str)
    assert ground == ['g1'] and {frozenset(p[2]) for p in parts if p[1] == 'W'} >= {frozenset(('g1', 'g2')), frozenset(('g2', 'g3'))}
    assert figures.overlaps(figures.render('circuit', spec)) == 0


def test_circuit_ground_symbol_never_sits_on_a_line():
    spec = {'nodes': LOOP, 'parts': [['V1', 'V', 'a', 'g'], ['R1', 'R', 'a', 'b'], ['R2', 'R', 'b', 'h'], ['', 'W', 'g', 'h']], 'ground': ['b']}
    with pytest.raises(ValueError, match='line going down'): figures.render('circuit', spec)


def test_circuit_transistors_and_transformer_draw_without_collisions():
    bjt = {'nodes': {'vcc': [3, 5], 'b': [0, 2], 'g': [0, -1.5], 'g2': [3, -1.5]}, 'terminals': {'vcc': '+12 V'}, 'ground': ['g2'],
           'parts': [['Q1', 'npn', 'bb', 'cc', 'ee', 'Q₁\nβ = 100', {'at': [3, 2]}], ['RC', 'R', 'vcc', 'cc', '2 kΩ'], ['RB', 'R', 'b', 'bb', '100 kΩ', {'current': 'I_B'}],
                     ['VB', 'V', 'b', 'g', '5 V'], ['RE', 'R', 'ee', 'g2', '1 kΩ'], ['', 'W', 'g', 'g2']]}
    fet = {'nodes': {'vdd': [5, 5], 'r': [5, 3.5], 'gnd': [5, -1], 'mx': [2, 1], 'nx': [2, -1]}, 'terminals': {'vdd': 'V_DD'}, 'ground': ['gnd'],
           'parts': [['T1', 'xfmr', 'a', 'a0', 'm', 'n', '1:2', {'at': [1, 1]}], ['M1', 'nmos', 'gg', 'dd', 'ss', 'M₁', {'at': [5, 1]}], ['Vp', 'Vac', 'a', 'a0', 'v_p'],
                     ['', 'W', 'm', 'mx'], ['', 'W', 'mx', 'gg'], ['', 'W', 'n', 'nx'], ['', 'W', 'nx', 'gnd'], ['', 'W', 'ss', 'gnd'], ['RD', 'R', 'vdd', 'r', 'R_D'], ['', 'W', 'r', 'dd']]}
    for spec in (bjt, fet): assert figures.overlaps(figures.render('circuit', spec)) == 0


def test_labels_written_as_latex_read_as_text():
    assert figures.text_label(r'X(j\omega)') == 'X(jω)' and figures.text_label('{1,2}') == '{1,2}'
    assert figures.text_label(r'base $e^{-2t}u(t)') == r'base $e^{-2t}u(t)$'          # missing closing $ (Fourier PDF, page 11)
    assert figures.text_label(r'$\nosuchcommand{x}$ y') == 'nosuchcommandx y'              # maths that cannot draw: text


def test_annotations_stay_clear_of_the_legend_and_each_other(tmp_path):
    import matplotlib.pyplot as plt
    spec = {'curves': [{'expr': 'x', 'range': [0, 1], 'label': 'a long legend label'}, {'expr': '1-x', 'range': [0, 1], 'label': 'another label'}],
            'annotations': [{'xy': [0.8, 0.8], 'text': 'note one', 'xytext': [0.8, 1.2]}, {'xy': [0.8, 0.8], 'text': 'note two', 'xytext': [0.8, 1.2]}],
            'xlabel': 'x'}
    shown = []
    real = figures.save
    figures.save = lambda fig, out: shown.append(fig) or real(fig, out)
    try: figures.plot(figures.labels(spec), str(tmp_path / 'a.png'))
    finally: figures.save = real
    fig = shown[0]; ax = fig.axes[0]; r = fig.canvas.get_renderer()
    import matplotlib.text
    boxes = [t.update_positions(r) or matplotlib.text.Text.get_window_extent(t, r) for t in ax.texts] + [ax.get_legend().get_window_extent(r)]   # text, not arrows
    assert not any(a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1:])


@pytest.mark.parametrize('title,kind,spec', SME_FIGURES, ids=[a[0][:40] for a in SME_FIGURES])
def test_reviewed_figures_have_no_overlapping_labels(title, kind, spec):
    """Figures rebuilt from the PDFs SMEs reviewed: after placement no label sits on another label (lines may still be crossed
    where nothing else is possible, which the count below would show)."""
    assert figures.overlaps(figures.render(kind, spec)) <= 1, title


def test_a_carrier_too_fast_to_read_is_refused_not_aliased(tmp_path):
    with pytest.raises(ValueError, match='illustrative frequencies'):
        figures.plot(figures.labels(TOO_FAST[1]), str(tmp_path / 'f.png'))


def test_a_curve_drawn_in_parts_keeps_one_colour_and_one_legend_entry(tmp_path):
    import matplotlib.pyplot as plt
    figures.brand(); fig, ax = plt.subplots()
    figures._axes(fig, ax, figures.labels(SME_FIGURES[3][2]))         # raised cosine: two parts per roll-off factor
    by_label = {}
    for ln in ax.lines: by_label.setdefault(ln.get_label().lstrip('_'), set()).add(ln.get_color())
    colours = [ln.get_color() for ln in ax.lines]
    assert colours[0] == colours[1] and colours[2] == colours[3] and colours[0] != colours[2]
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ['α=0.10', 'α=0.25']
    plt.close(fig)


def test_subscripts_typed_as_text_become_maths():
    """Seen in a CE PDF: "Σ_i=1^n x_iK_i=1", "N_min", "W_0/12", "L_0/D" printed with their underscores."""
    assert TEX.plain('use Σ_i=1^n x_iK_i=1 now') == r'use $\sum_{i=1}^{n}$ $x_iK_i$=1 now'
    assert TEX.plain('N_min = 6.43 and W = W_0/12') == '$N_{min}$ = 6.43 and W = $W_0$/12'
    assert TEX.plain('P_i^sat') == '$P_i^{sat}$'
    assert TEX.plain('snake_case, k_means and name_final.pdf stay') == 'snake_case, k_means and name_final.pdf stay'
    assert TEX.plain('already $x_i$ in maths') == 'already $x_i$ in maths'


def test_a_flowchart_label_is_shrunk_to_its_box_and_a_short_one_is_left_alone():
    import fig_diagrams as D
    svg = lambda w, t: f'<rect x="0" y="0" width="{w}" height="22.5" fill="#FFF6CC"/><text x="50" y="5" style="text-anchor:middle;font-size:15px;font-family:Arial">{t}</text>'
    assert 'font-size:15px' not in D._fit_labels(svg(80, 'scheduler dispatches the process'))       # far wider than its box
    assert 'font-size:15px' in D._fit_labels(svg(300, 'I/O'))


def test_block_diagram_boxes_and_arrows_grow_with_their_labels(tmp_path):
    import fig_diagrams as D
    assert D._width('Sensor and signal conditioner H(s)') > D._width('H(s)') and D._width('a\nlonger line') == D._width('longer line')
    figures.render('block', {'chain': [{'el': 'in', 'label': 'r'}, {'el': 'sum', 'id': 's'}, {'el': 'box', 'id': 'p', 'label': 'Plant', 'edge': 'a long arrow label here'}, {'el': 'out', 'label': 'y'}],
                             'feedback': [{'from': 'p', 'to': 's', 'box': 'Sensor and signal conditioner H(s)', 'sign': '−'}]}, str(tmp_path / 'b.png'))

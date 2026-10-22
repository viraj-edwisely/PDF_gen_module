"""Figures computed from physics give textbook answers, and every computed or geometry figure draws with readable labels.
python -m pytest tests"""
import os, sys
import numpy as np
import pytest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), 'render')]
import figures, fig_physics as P
from physics_figures import PHYSICS
from sme_geometry import SME_GEOMETRY
from process_figures import PROCESS

SSB = {'length': 4, 'supports': [{'x': 0, 'type': 'pin'}, {'x': 4, 'type': 'roller'}]}


def at(x, y, xv, side=1):
    return float(y[int(np.searchsorted(x, xv + side * 1e-6))])


def test_beam_diagrams_match_the_textbook():
    x, V, M, r = P.beam_solution({**SSB, 'loads': [{'type': 'udl', 'x1': 0, 'x2': 4, 'w': 5}]})
    assert M.max() == pytest.approx(5 * 4 ** 2 / 8) and [v for *_, v in r] == pytest.approx([10, 10])            # wL²/8
    x, V, M, r = P.beam_solution({'length': 3, 'supports': [{'x': 0, 'type': 'fixed'}], 'loads': [{'type': 'point', 'x': 3, 'P': 10}]})
    assert M[1] == pytest.approx(-30, abs=1e-6) and at(x, V, 1.5) == pytest.approx(10)                          # cantilever: -PL, V = P
    x, V, M, r = P.beam_solution({'length': 6, 'supports': [{'x': 0, 'type': 'pin'}, {'x': 4, 'type': 'roller'}], 'loads': [{'type': 'point', 'x': 6, 'P': 10}]})
    assert [v for *_, v in r] == pytest.approx([-5, 15]) and at(x, M, 4) == pytest.approx(-20, abs=0.05)                   # overhang
    x, V, M, r = P.beam_solution({'length': 6, 'supports': [{'x': 0, 'type': 'pin'}, {'x': 6, 'type': 'roller'}], 'loads': [{'type': 'moment', 'x': 3, 'M': 12}]})
    assert at(x, M, 3, -1) == pytest.approx(6, abs=0.01) and at(x, M, 3) == pytest.approx(-6, abs=0.01)          # a couple: jump of M
    x, V, M, r = P.beam_solution({'length': 6, 'supports': [{'x': 0, 'type': 'pin'}, {'x': 6, 'type': 'roller'}], 'loads': [{'type': 'uvl', 'x1': 0, 'x2': 6, 'w1': 0, 'w2': 6}]})
    assert M.max() == pytest.approx(6 * 6 * 6 / (9 * 3 ** 0.5), rel=1e-4)                                      # wL²/(9√3)
    with pytest.raises(ValueError, match='determinate'):
        P.beam_solution({'length': 6, 'supports': [{'x': 0, 'type': 'fixed'}, {'x': 6, 'type': 'roller'}], 'loads': []})


@pytest.mark.parametrize('title,kind,spec', PHYSICS + SME_GEOMETRY + PROCESS, ids=[a[0][:40] for a in PHYSICS + SME_GEOMETRY + PROCESS])
def test_computed_and_geometry_figures_draw_readably(title, kind, spec):
    if kind == 'cycle' and spec.get('fluid') not in ('air', None): pytest.importorskip('CoolProp')
    assert figures.overlaps(figures.render(kind, spec)) <= 2, title


def test_bad_inputs_are_explained():
    with pytest.raises(ValueError, match='p-h'): figures.render('cycle', {'fluid': 'air', 'diagram': 'ph', 'states': [{'name': '1', 'p': 100, 'T': 300}], 'processes': []})
    with pytest.raises(ValueError, match='waveform type'): figures.render('waveform', {'type': 'QAM-256'})


def test_mccabe_thiele_matches_the_hand_construction():
    s = P.mccabe_solution({'alpha': 2.0, 'xD': 0.8, 'xF': 0.4, 'xB': 0.1, 'q': 1, 'R': 2.0})
    assert (s['N'], s['feed']) == (10, 5) and s['xi'] == pytest.approx(0.4) and s['yi'] == pytest.approx(2 / 3 * 0.4 + 0.8 / 3)     # the rectifying line at x = xF
    assert s['x'][1] == pytest.approx(0.8 / 1.2) and s['N'] - 1 < s['N_exact'] <= s['N']        # the first stage steps x = y / (alpha - (alpha - 1) y)
    wet = P.mccabe_solution({'alpha': 2.0, 'xD': 0.8, 'xF': 0.4, 'xB': 0.1, 'q': 0.5, 'R': 2.0})
    assert wet['xi'] < 0.4 and wet['N'] >= 10                                                   # a partly vaporised feed moves the q-line left


def test_mccabe_thiele_refuses_a_reflux_below_the_minimum():
    with pytest.raises(ValueError, match='minimum reflux'): P.mccabe_solution({'alpha': 2.5, 'xD': 0.95, 'xF': 0.5, 'xB': 0.05, 'q': 1, 'R': 1.0})
    with pytest.raises(ValueError, match='xB < xF < xD'): P.mccabe_solution({'alpha': 2.5, 'xD': 0.4, 'xF': 0.5, 'xB': 0.05, 'R': 2})


def test_process_figure_explains_bad_input():
    node = lambda i, at, t='box': {'id': i, 'type': t, 'label': i, 'at': at}
    with pytest.raises(ValueError, match='unknown equipment type'): figures.render('process', {'nodes': [node('A', [0, 0], 'reboiler')], 'streams': []})
    with pytest.raises(ValueError, match='share a grid cell'): figures.render('process', {'nodes': [node('A', [0, 0]), node('B', [0, 0])], 'streams': []})
    with pytest.raises(ValueError, match='unknown "id"'): figures.render('process', {'nodes': [node('A', [0, 0])], 'streams': [{'from': 'A', 'to': 'Z'}]})


def test_binary_vle_matches_benzene_toluene_data():
    v = P.antoine_vle({'components': [{'name': 'Toluene', 'antoine': [6.95464, 1344.8, 219.482]}, {'name': 'Benzene', 'antoine': [6.90565, 1211.033, 220.79]}], 'P': 760, 'tie': 0.4})
    assert v['names'] == ['Benzene', 'Toluene']                                            # the component that boils first is component 1
    assert v['Tb'] == pytest.approx([80.1, 110.6], abs=0.1) and 2.3 < v['alpha'] < 2.6
    assert v['tie']['T'] == pytest.approx(95.1, abs=0.2) and v['tie']['y'] == pytest.approx(0.62, abs=0.01)     # x = 0.4: bubble point about 95 degC, y about 0.62
    assert v['y'][0] == 0 and v['y'][-1] == pytest.approx(1)

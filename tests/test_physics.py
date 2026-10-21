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


@pytest.mark.parametrize('title,kind,spec', PHYSICS + SME_GEOMETRY, ids=[a[0][:40] for a in PHYSICS + SME_GEOMETRY])
def test_computed_and_geometry_figures_draw_readably(title, kind, spec):
    if kind == 'cycle' and spec.get('fluid') not in ('air', None): pytest.importorskip('CoolProp')
    assert figures.overlaps(figures.render(kind, spec)) <= 2, title


def test_bad_inputs_are_explained():
    with pytest.raises(ValueError, match='p-h'): figures.render('cycle', {'fluid': 'air', 'diagram': 'ph', 'states': [{'name': '1', 'p': 100, 'T': 300}], 'processes': []})
    with pytest.raises(ValueError, match='waveform type'): figures.render('waveform', {'type': 'QAM-256'})

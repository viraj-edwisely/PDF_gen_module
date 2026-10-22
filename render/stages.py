"""Stage-by-stage separation maths with no drawing (numpy and scipy only), shared by the figures (fig_physics.py) and the content checks
(content.py): the McCabe-Thiele construction and binary vapour-liquid equilibrium from Antoine constants."""
import numpy as np


def equilibrium(spec):
    """y*(x) and its inverse x*(y): constant relative volatility "alpha", or interpolated from a table "eq": {"x": [...], "y": [...]}."""
    if spec.get('eq'):
        from scipy.interpolate import PchipInterpolator              # smooth and monotonic, so the curve and its inverse agree
        xs, ys = (np.asarray(spec['eq'][k], float) for k in ('x', 'y'))
        order = np.argsort(xs); xs, ys = xs[order], ys[order]
        if np.any(np.diff(xs) <= 0) or np.any(np.diff(ys) <= 0): raise ValueError('the tabulated equilibrium must have x and y both rising')
        return PchipInterpolator(xs, ys), PchipInterpolator(ys, xs)
    a = float(spec['alpha'])
    if a <= 1: raise ValueError('"alpha" is the relative volatility of the more volatile component: it must be above 1')
    return (lambda x: a * x / (1 + (a - 1) * x)), (lambda y: y / (a - (a - 1) * y))


def mccabe_solution(spec):
    """The McCabe-Thiele construction: where the operating lines meet on the q-line, and the equilibrium stages stepped from
    xD down to xB. Returns {"xi", "yi", "N" (whole stages), "N_exact" (with the last step as a fraction), "feed" (the stage
    where the operating line changes), "x", "y" (the staircase corners)}."""
    yeq, xeq = equilibrium(spec)
    xD, xB, xF, R, q = (float(spec.get(k, 1 if k == 'q' else 0)) for k in ('xD', 'xB', 'xF', 'R', 'q'))
    if not 0 < xB < xF < xD < 1: raise ValueError('McCabe-Thiele needs 0 < xB < xF < xD < 1')
    rect = lambda x: R / (R + 1) * x + xD / (R + 1)
    xi = xF if abs(q - 1) < 1e-9 else (xD / (R + 1) + xF / (q - 1)) / (q / (q - 1) - R / (R + 1))
    yi = rect(xi)
    if not xB < xi < xD or yi >= yeq(xi): raise ValueError('the operating lines meet on or above the equilibrium curve: R is below the minimum reflux (a pinch)')
    strip = lambda x: xB + (yi - xB) / (xi - xB) * (x - xB)
    xs, ys, feed, last = [xD], [xD], None, [xD]
    for n in range(1, 61):
        x = float(xeq(ys[-1]))                           # across to the equilibrium curve: stage n
        if x > last[-1] - 1e-9: raise ValueError('the staircase stops moving: the operating line touches the equilibrium curve (a pinch)')
        xs.append(x); ys.append(ys[-1]); last.append(x)
        feed = feed or (n if x <= xi else None)
        if x <= xB: return {'xi': xi, 'yi': yi, 'N': n, 'N_exact': n - 1 + (last[-2] - xB) / (last[-2] - x), 'feed': feed or n, 'x': xs, 'y': ys}
        xs.append(x); ys.append(float(strip(x) if feed else rect(x)))          # down to the operating line
    raise ValueError('more than 60 stages are needed: R is too close to the minimum reflux')


def antoine_vle(spec):
    """Binary vapour-liquid equilibrium at constant pressure from Antoine constants (log10 P/mmHg = A - B / (C + T/degC)), ideal liquid
    and vapour. The component that boils first is component 1. Returns {"names", "Tb" (boiling points), "x", "T", "y" (the bubble and
    dew curves against the liquid mole fraction x of component 1), "alpha" (mean relative volatility), "tie" (x, y, T at spec["tie"])}."""
    from scipy.optimize import brentq
    comps = spec.get('components') or []
    if len(comps) != 2 or any(len(c.get('antoine') or []) != 3 for c in comps): raise ValueError('"components" needs two entries, each with "antoine": [A, B, C]')
    P = float(spec.get('P', 760))
    psat = lambda c, T: 10 ** (c['antoine'][0] - c['antoine'][1] / (c['antoine'][2] + T))
    tb = [c['antoine'][1] / (c['antoine'][0] - np.log10(P)) - c['antoine'][2] for c in comps]
    comps, tb = zip(*sorted(zip(comps, tb), key=lambda p: p[1]))
    lo, hi = tb[0] - 1, tb[1] + 1
    def at(x):
        T = brentq(lambda t: x * psat(comps[0], t) + (1 - x) * psat(comps[1], t) - P, lo, hi)
        return T, x * psat(comps[0], T) / P
    xs = np.linspace(0, 1, 101)
    T, y = np.array([at(x) for x in xs]).T
    out = {'names': [c.get('name', f'Component {i + 1}') for i, c in enumerate(comps)], 'Tb': list(tb), 'x': xs, 'T': T, 'y': y,
           'alpha': float(np.mean([psat(comps[0], t) / psat(comps[1], t) for t in T]))}
    if spec.get('tie') is not None:
        x = float(spec['tie'])
        if not 0 < x < 1: raise ValueError('"tie" is a liquid mole fraction between 0 and 1')
        t, yy = at(x); out['tie'] = {'x': x, 'y': yy, 'T': t}
    return out

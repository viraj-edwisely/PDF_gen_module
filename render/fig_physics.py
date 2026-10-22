"""Figure kinds whose shape is set by physics, so the code computes it and the model gives only the inputs: a beam with
its shear-force and bending-moment diagrams, Mohr's circle, the pressure diagram on a submerged plate, modulation
waveforms and spectra, thermodynamic cycles (ideal gas, and steam and refrigerants through CoolProp), and control-system
responses. A wrong shape (a straight BMD under a UDL, an ideal-gas isentrope drawn as a straight line) cannot happen.
Each kind's exact spec is its docstring: figures.reference() gives it to the model."""
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon
from figstyle import PURPLE, LAV, INK, GREY, PALETTE, ISSUES, brand, save, _fmt
import labels as LBL
from stages import antoine_vle, equilibrium, mccabe_solution

TEAL, GOLD, PINK = '#2E8B87', '#D9A400', '#B5487A'


def _num(x, default=None):
    """A number from a value or a label ("10 kN" -> 10)."""
    if isinstance(x, (int, float)): return float(x)
    m = re.search(r'-?\d+(?:\.\d+)?', str(x or ''))
    return float(m.group()) if m else default


def _plot(spec):
    """A spec drawn by the plot kind (imported here: figures imports this module)."""
    import figures
    return spec, figures.plot


# ---------------------------------------------------------------- beam, SFD, BMD
def _draw_beam(ax, spec, notes):
    """The loaded beam: supports, loads, point names and dimension lines. Label annotations are added to notes."""
    L = float(spec['length']); s = 6.4 / L
    ax.set_xlim(-0.08 * L, 1.08 * L); ax.set_ylim(-1.3, 1.75); ax.axis('off')
    lab = lambda text, xy, off=(0, 3), **kw: notes.append(ax.annotate(str(text), xy, textcoords='offset points', xytext=off, ha='center', fontsize=8.5, color=INK, **kw)) if text else None
    secs = spec.get('sections')        # a stepped shaft or beam: [[x1, x2, diameter or depth, "label"], ...]
    if secs:
        dmax = max(float(sc[2]) for sc in secs)
        for sc in secs:
            hh = 0.34 * float(sc[2]) / dmax
            ax.add_patch(plt.Rectangle((sc[0], -hh / 2), sc[1] - sc[0], hh, color=PURPLE, ec='white', lw=0.6))
            if len(sc) > 3: lab(sc[3], ((sc[0] + sc[1]) / 2, -0.2), (0, -10), va='top')
    else: ax.add_patch(plt.Rectangle((0, -0.08), L, 0.16, color=PURPLE))
    for sp in spec.get('supports', []):
        x, t = float(sp['x']), sp.get('type', 'pin')
        if t == 'fixed':
            sgn = -1 if x <= 0.01 * L else 1
            ax.plot([x, x], [-0.45, 0.45], color=INK, lw=2)
            for yy in np.linspace(-0.4, 0.4, 7): ax.plot([x, x + sgn * 0.04 * L], [yy, yy - 0.1], color=INK, lw=0.8)
        elif t == 'hinge':
            ax.add_patch(plt.Circle((x, 0), 0.025 * L, facecolor='white', edgecolor=INK, lw=1.2, zorder=4))
        else:
            w = 0.035 * L
            ax.add_patch(plt.Polygon([[x, -0.08], [x - w, -0.42], [x + w, -0.42]], facecolor=LAV, edgecolor=INK, lw=1.2))
            if t == 'roller':
                for dx in (-w * 0.55, 0, w * 0.55): ax.add_patch(plt.Circle((x + dx, -0.48), 0.012 * L, facecolor='white', edgecolor=INK, lw=1))
                ax.plot([x - 1.4 * w, x + 1.4 * w], [-0.56, -0.56], color=INK, lw=1)
            else: ax.plot([x - 1.4 * w, x + 1.4 * w], [-0.42, -0.42], color=INK, lw=1)
    for ld in spec.get('loads', []):
        t = ld['type']
        if t == 'point':
            ax.annotate('', (ld['x'], 0.1), xytext=(ld['x'], 1.05), arrowprops=dict(arrowstyle='-|>', color=GOLD, lw=2.2))
            lab(ld.get('label') or f"{_fmt(_num(ld.get('P'), 0))} {spec.get('force_unit', 'kN')}", (ld['x'], 1.1))
        elif t in ('udl', 'uvl'):
            x1, x2 = float(ld['x1']), float(ld['x2']); w1, w2 = (float(ld.get('w1', 0)), float(ld.get('w2', 1))) if t == 'uvl' else (1, 1)
            h = lambda x: 0.2 + 0.5 * (w1 + (w2 - w1) * (x - x1) / (x2 - x1)) / (max(abs(w1), abs(w2)) or 1)
            ax.fill_between([x1, x2], [0.1, 0.1], [h(x1), h(x2)], color=TEAL, alpha=0.15, lw=0)
            ax.plot([x1, x2], [h(x1), h(x2)], color=TEAL, lw=1.4)
            for x in np.linspace(x1, x2, max(4, int((x2 - x1) * s / 0.35))): ax.annotate('', (x, 0.1), xytext=(x, h(x)), arrowprops=dict(arrowstyle='-|>', color=TEAL, lw=1))
            unit = f"{spec.get('force_unit', 'kN')}/{spec.get('length_unit', 'm')}"
            lab(ld.get('label') or (f"{_fmt(_num(ld.get('w'), 0))} {unit}" if t == 'udl' else f"{_fmt(w1)} to {_fmt(w2)} {unit}"), ((x1 + x2) / 2, max(h(x1), h(x2)) + 0.04))
        elif t == 'moment':
            r = 0.05 * L; ccw = ld.get('ccw', True)
            ax.add_patch(FancyArrowPatch((ld['x'] + r, 0.25), (ld['x'] - r, 0.25), connectionstyle=f'arc3,rad={0.9 if ccw else -0.9}',
                                         arrowstyle='-|>', mutation_scale=10, color=PINK, lw=1.8))
            lab(ld.get('label') or f"{_fmt(_num(ld.get('M'), 0))} {spec.get('force_unit', 'kN')}·{spec.get('length_unit', 'm')}", (ld['x'], 0.62))
    for name, x in (spec.get('points') or {}).items():
        ax.text(x, -0.72 if spec.get('dims') else -0.68, name, ha='center', va='top', fontsize=9, color=PURPLE, fontweight='bold')
    for d in spec.get('dims', []):
        x1, x2, txt = d; y = -1.02
        ax.annotate('', (x1, y), xytext=(x2, y), arrowprops=dict(arrowstyle='<->', color=GREY, lw=0.9))
        ax.text((x1 + x2) / 2, y - 0.06, txt, ha='center', va='top', fontsize=8, color=INK)


def beam_solution(spec):
    """Reactions, and shear force V(x) and bending moment M(x) on a fine grid, for a statically determinate beam
    (pin + roller anywhere, overhangs included, or one fixed end). Loads point down when positive; moment loads are
    counter-clockwise when "ccw" is true; sagging moment is positive. Returns (x, V, M, reactions)."""
    L = float(spec['length'])
    sup = spec.get('supports', [])
    if any(s.get('type') == 'hinge' for s in sup): raise ValueError('a beam with an internal hinge: draw its SFD/BMD with the plot kind')
    unknown = [('F', float(s['x'])) for s in sup if s.get('type') in ('pin', 'roller', 'fixed')] + [('C', float(s['x'])) for s in sup if s.get('type') == 'fixed']
    if len(unknown) != 2: raise ValueError('only statically determinate beams (pin and roller, or one fixed end) get computed diagrams; '
                                          'draw an indeterminate beam\'s SFD/BMD with the plot kind')
    pts, dist, cps = [], [], []                         # point loads (x, P), distributed (x1, x2, w1, w2), couples (x, C ccw)
    for ld in spec.get('loads', []):
        t = ld['type']
        if t == 'point': pts.append((float(ld['x']), _num(ld.get('P', ld.get('label')), 0)))
        elif t == 'udl': w = _num(ld.get('w', ld.get('label')), 0); dist.append((float(ld['x1']), float(ld['x2']), w, w))
        elif t == 'uvl': dist.append((float(ld['x1']), float(ld['x2']), float(ld.get('w1', 0)), float(ld.get('w2', 0))))
        elif t == 'moment': m = _num(ld.get('M', ld.get('label')), 0); cps.append((float(ld['x']), m if ld.get('ccw', True) else -m))
    total = sum(P for _, P in pts) + sum((b - a) * (w1 + w2) / 2 for a, b, w1, w2 in dist)
    moment = sum(P * x for x, P in pts) + sum((b - a) * (w1 * (2 * a + b) + w2 * (a + 2 * b)) / 6 for a, b, w1, w2 in dist) - sum(c for _, c in cps)
    A = np.array([[1.0 if k == 'F' else 0.0 for k, _ in unknown], [x if k == 'F' else 1.0 for k, x in unknown]])
    try: r = np.linalg.solve(A, [total, moment])
    except np.linalg.LinAlgError: raise ValueError('the supports cannot hold the beam (both at the same point)')
    reactions = [(k, x, v) for (k, x), v in zip(unknown, r)]
    eps = 1e-9 * L
    jumps = [x for x, _ in pts] + [x for x, _ in cps] + [x for k, x, _ in reactions] + [v for a, b, *_ in dist for v in (a, b)]
    x = np.unique(np.concatenate([np.linspace(0, L, 2001), np.clip([j + d for j in jumps for d in (-eps, eps)], 0, L)]))
    w = np.zeros_like(x)
    for a, b, w1, w2 in dist:
        on = (x >= a) & (x <= b)
        w[on] += w1 + (w2 - w1) * (x[on] - a) / (b - a)
    W = np.concatenate([[0], np.cumsum((w[1:] + w[:-1]) / 2 * np.diff(x))])          # load carried up to x
    V = -W.copy()
    for k, xr, v in reactions:
        if k == 'F': V += v * (x > xr - eps / 2)
    for xp, P in pts: V -= P * (x > xp + eps / 2)
    M = np.concatenate([[0], np.cumsum((V[1:] + V[:-1]) / 2 * np.diff(x))])
    for k, xr, v in reactions:
        if k == 'C': M -= v * (x > xr - eps / 2)
    for xc, c in cps: M -= c * (x > xc + eps / 2)
    return x, V, M, reactions


def beam(spec, out):
    """spec: {"length": L, "supports": [{"x": 0, "type": "pin"|"roller"|"fixed"|"hinge"}],
              "loads": [{"type": "point", "x": 2, "P": 10}, {"type": "udl", "x1": 0, "x2": 4, "w": 5},
                        {"type": "uvl", "x1": 0, "x2": 4, "w1": 0, "w2": 6}, {"type": "moment", "x": 3, "M": 20, "ccw": true}],
              "force_unit": "kN", "length_unit": "m", "diagrams": ["sfd", "bmd"] (optional),
              "dims": [[x1, x2, "label"], ...] (dimension lines under the beam), "points": {"A": 0, "B": 6},
              "sections": [[x1, x2, diameter, "d = 40 mm"], ...] (a stepped shaft or beam, each part to its relative size)}
    Loads are numbers (P in force units, w per length, M in force x length; positive P and w act downward). Labels are
    written from them (a load may also give its own "label").
    "diagrams": the app computes the reactions and draws the shear-force and bending-moment diagrams under the beam with
    their true shapes (linear under a UDL, parabolic BM, jumps at point loads and couples), marking the values at supports,
    loads, the zero-shear point and the maximum moment. Only for determinate beams (pin + roller, overhangs allowed, or a
    cantilever). Never draw an SFD or BMD as a plot of a formula you worked out: use "diagrams".
    Shafts in torsion are beams too: a fixed support, a "moment" load for the torque, "sections" for the steps."""
    brand()
    want = [d for d in spec.get('diagrams', []) if d in ('sfd', 'bmd')]
    if not want:
        fig, ax = plt.subplots(figsize=(6.6, 2.3)); notes = []
        _draw_beam(ax, spec, notes)
        ISSUES.append(LBL.place(fig, ax, notes, offsets=LBL.UP_DOWN, lines=False))
        return save(fig, out)
    x, V, M, reactions = beam_solution(spec)
    L = float(spec['length']); fu, lu = spec.get('force_unit', 'kN'), spec.get('length_unit', 'm')
    fig, axes = plt.subplots(1 + len(want), 1, figsize=(6.6, 2.3 + 1.7 * len(want)), sharex=True, gridspec_kw={'height_ratios': [2.3] + [1.7] * len(want)})
    notes = []
    _draw_beam(axes[0], spec, notes)
    for k, xr, v in reactions:          # reactions under the supports
        if k == 'F': notes.append(axes[0].annotate(f'R = {_fmt(round(v, 2))} {fu}', (xr, -0.56), textcoords='offset points', xytext=(0, -24), ha='center', fontsize=7.5, color=GREY))
    ISSUES.append(LBL.place(fig, axes[0], notes, offsets=LBL.UP_DOWN, lines=False))
    keys = sorted({0.0, L} | {float(s['x']) for s in spec.get('supports', [])} | {float(l_['x']) for l_ in spec.get('loads', []) if 'x' in l_}
                  | {float(v) for l_ in spec.get('loads', []) for v in (l_.get('x1'), l_.get('x2')) if v is not None})
    for ax, what in zip(axes[1:], want):
        y, colour, name = (V, TEAL, f'V ({fu})') if what == 'sfd' else (M, PURPLE, f'M ({fu}·{lu})')
        ax.plot(x, y, color=colour, lw=1.8); ax.fill_between(x, y, 0, color=colour, alpha=0.15, lw=0)
        ax.axhline(0, color=INK, lw=0.8); ax.set_ylabel(name); ax.spines['bottom'].set_visible(False)
        span = max(np.abs(y).max(), 1e-9); ax.set_ylim(min(y.min(), 0) - 0.25 * span, max(y.max(), 0) + 0.25 * span)
        cands = []                      # values either side of each key point (a jump shows both), and the extremes
        for xk in keys:
            for side in (-1, 1):
                i = int(np.clip(np.searchsorted(x, xk + side * 2e-9 * L), 0, len(x) - 1))
                cands.append((float(x[i]), float(y[i])))
        cands += [(float(x[int(np.argmax(y))]), float(y.max())), (float(x[int(np.argmin(y))]), float(y.min()))]
        marks = {}
        for xx, v in cands:
            if abs(v) > 0.01 * span and all(abs(v - u) > 0.02 * span or abs(xx - xo) > 0.02 * L for xo, u in marks.items()): marks[xx] = round(v, 2)
        if what == 'sfd':               # where the shear changes sign inside a distributed load: the maximum moment is there
            s = np.sign(np.round(V, 9)); zero = [x[i] for i in range(1, len(x)) if s[i] * s[i - 1] < 0 and abs(V[i] - V[i - 1]) < 0.01 * span]
            for xz in zero:
                ax.plot(xz, 0, 'o', color=INK, ms=4); notes2 = [ax.annotate(f'V = 0 at x = {_fmt(round(xz, 3))} {lu}', (xz, 0), textcoords='offset points', xytext=(6, 8), fontsize=7.5, color=INK)]
                ISSUES.append(LBL.place(fig, ax, notes2))
        else:
            for i in {int(np.argmax(M)), int(np.argmin(M))}:
                if abs(M[i]) > 0.01 * span: ax.plot(x[i], M[i], 'o', color=PURPLE, ms=4)
        vals = [ax.annotate(_fmt(v), (xx, v), textcoords='offset points', xytext=(0, 5 if v >= 0 else -12), ha='center', fontsize=7.5, color=INK) for xx, v in marks.items()]
        ISSUES.append(LBL.place(fig, ax, vals, offsets=LBL.UP_DOWN + [(10, 4), (-10, 4), (10, -10), (-10, -10)]))
        ax.set_title('Shear force diagram' if what == 'sfd' else 'Bending moment diagram (sagging positive)', fontsize=9)
    axes[-1].set_xlabel(f'x ({lu})'); axes[-1].tick_params(labelbottom=True)
    return save(fig, out)


# ---------------------------------------------------------------- Mohr's circle
def mohr(spec, out):
    """spec: {"sx": 80, "sy": -20, "txy": 30, "unit": "MPa"}
    Mohr's circle of plane stress, computed: centre, radius, principal stresses σ1 and σ2, maximum in-plane shear τmax and
    the angle 2θp, with the points X (σx, τxy) and Y (σy, −τxy) marked (τ plotted positive upward). Tension positive."""
    sx, sy, t = (float(spec[k]) for k in ('sx', 'sy', 'txy'))
    u = spec.get('unit', 'MPa')
    c, r = (sx + sy) / 2, float(np.hypot((sx - sy) / 2, t))
    p2 = float(np.degrees(np.arctan2(2 * t, sx - sy)))
    f = lambda v: _fmt(round(v, 2))
    ps, plot = _plot({'equal': True, 'axes_at_zero': True, 'xlabel': f'σ ({u})', 'ylabel': f'τ ({u})', 'size': [5.2, 4.2], 'legend': False,
                      'curves': [{'param': [f'{c} + {r}*cos(t)', f'{r}*sin(t)'], 'range': [0, 6.2832]},
                                 {'x': [sx, sy], 'y': [t, -t], 'style': '--', 'lw': 1.2},
                                 {'param': [f'{c} + {0.3 * r}*cos(t)', f'{0.3 * r}*sin(t)'], 'range': sorted([0, float(np.radians(p2))]), 'lw': 1}],
                      'points': [{'x': sx, 'y': t, 'label': f'X ({f(sx)}, {f(t)})'}, {'x': sy, 'y': -t, 'label': f'Y ({f(sy)}, {f(-t)})'},
                                 {'x': c + r, 'y': 0, 'label': f'σ₁ = {f(c + r)}'}, {'x': c - r, 'y': 0, 'label': f'σ₂ = {f(c - r)}'},
                                 {'x': c, 'y': r, 'label': f'τmax = {f(r)}'}, {'x': c, 'y': 0, 'label': f'C = {f(c)}', 'color': 'grey'}],
                      'annotations': [{'xy': [c + 0.3 * r * np.cos(np.radians(p2 / 2)), 0.3 * r * np.sin(np.radians(p2 / 2))], 'text': f'2θp = {f(abs(p2))}°'}]})
    return plot(ps, out)


# ---------------------------------------------------------------- pressure on a submerged plate
def pressure(spec, out):
    """spec: {"top_depth": 0.5, "length": 1.5 (along the plate), "angle": 90 (degrees from the horizontal; 90 vertical,
              0 horizontal), "width": 1.0, "rho": 1000, "g": 9.81, "unit": "m"}
    A rectangular plate under a free surface with its pressure diagram (the pressure prism, normal to the plate, growing
    linearly with depth), the centroid G and the centre of pressure CP, all computed: h_c = h0 + (L/2) sin θ,
    F = ρ g h_c A, h_cp = h_c + I_G sin²θ / (A h_c). Depth grows downward. Use for every hydrostatic-force-on-a-plate figure."""
    brand()
    h0, L, th = float(spec['top_depth']), float(spec['length']), np.radians(float(spec.get('angle', 90)))
    b, rho, g = float(spec.get('width', 1)), float(spec.get('rho', 1000)), float(spec.get('g', 9.81))
    u = spec.get('unit', 'm')
    A, IG = b * L, b * L ** 3 / 12
    hc = h0 + L / 2 * np.sin(th)
    hcp = hc + IG * np.sin(th) ** 2 / (A * hc) if np.sin(th) > 1e-6 else hc
    F = rho * g * hc * A / 1000
    d = np.array([np.cos(th), np.sin(th)])            # along the plate, downward (depth positive)
    n = np.array([-d[1], d[0]])                       # normal to the plate, on the water side (upper left)
    top = np.array([0.0, h0]); bot = top + L * d
    pk = lambda depth: rho * g * depth / 1000
    scale = 0.55 * L / max(pk(bot[1]), 1e-9)
    fig, ax = plt.subplots(figsize=(5.6, 4.2)); notes = []
    span_x = [min(top[0], bot[0]) - 0.9 * L, max(top[0], bot[0]) + 0.4 * L]
    ax.plot(span_x, [0, 0], color=TEAL, lw=1.2); ax.plot(np.mean(span_x), 0, 'v', color=TEAL, ms=7)
    notes.append(ax.annotate('free surface', (span_x[1], 0), textcoords='offset points', xytext=(-4, 4), ha='right', fontsize=8, color=TEAL))
    ss = np.linspace(0, L, 9)
    edge = [top + s * d - n * pk(top[1] + s * d[1]) * scale for s in ss]
    ax.add_patch(Polygon([top] + edge + [bot], closed=True, facecolor=LAV, edgecolor='none', alpha=0.9, zorder=1))
    ax.plot(*np.array(edge).T, color=TEAL, lw=1.2)
    for s, e in zip(ss, edge):
        if np.linalg.norm(top + s * d - e) > 0.02 * L:
            ax.add_patch(FancyArrowPatch(e, top + s * d, arrowstyle='-|>', mutation_scale=8, color=TEAL, lw=0.9, zorder=3))
    ax.plot(*zip(top, bot), color=PURPLE, lw=5, solid_capstyle='butt', zorder=4)
    for pt, depth, name in ((top, h0, 'top'), (bot, bot[1], 'bottom')):
        notes.append(ax.annotate(f'p = {_fmt(round(pk(depth), 2))} kPa', tuple(pt - n * pk(depth) * scale), textcoords='offset points', xytext=(-6, 2), ha='right', fontsize=7.5, color=TEAL))
    sc = (hc - h0) / np.sin(th) if np.sin(th) > 1e-6 else L / 2
    scp = (hcp - h0) / np.sin(th) if np.sin(th) > 1e-6 else L / 2
    G, CP = top + sc * d, top + scp * d
    ax.plot(*G, 'o', color=INK, ms=5, zorder=6); ax.plot(*CP, 'o', color=GOLD, ms=6, zorder=6)
    dry = 14 * np.array([n[0], -n[1]]) / np.hypot(*n)        # the dry side of the plate, in points on the page (y drawn downward)
    ha = 'right' if dry[0] < 0 else 'left'
    notes.append(ax.annotate(f'G: h_c = {_fmt(round(hc, 3))} {u}', tuple(G), textcoords='offset points', xytext=tuple(dry + [0, 6]), ha=ha, fontsize=8, color=INK))
    notes.append(ax.annotate(f'CP: h_cp = {_fmt(round(hcp, 3))} {u}', tuple(CP), textcoords='offset points', xytext=tuple(dry - [0, 8]), ha=ha, fontsize=8, color=INK))
    ax.add_patch(FancyArrowPatch(CP - n * 0.35 * L, CP, arrowstyle='-|>', mutation_scale=14, color=GOLD, lw=2.2, zorder=5))
    notes.append(ax.annotate(f'F = {_fmt(round(F, 2))} kN', tuple(CP - n * 0.35 * L), textcoords='offset points', xytext=(-4, 6), ha='right', fontsize=8, color=INK))
    ax.annotate('', (top[0] + 0.12 * L + max(0, (bot - top)[0]), 0), xytext=(top[0] + 0.12 * L + max(0, (bot - top)[0]), h0),
                arrowprops=dict(arrowstyle='<->', color=GREY, lw=0.8)) if h0 > 0 else None
    if h0 > 0: notes.append(ax.annotate(f'h0 = {_fmt(h0)} {u}', (top[0] + 0.12 * L + max(0, (bot - top)[0]), h0 / 2), textcoords='offset points', xytext=(4, 0), fontsize=7.5, color=GREY))
    ax.set_aspect('equal', adjustable='datalim'); ax.invert_yaxis(); ax.axis('off'); ax.margins(0.1)
    ISSUES.append(LBL.place(fig, ax, notes))
    return save(fig, out)


# ---------------------------------------------------------------- modulation waveforms and spectra
def _bits_expr(bits, high, low):
    """An expression of x (time in bit periods) that is `high` during 1-bits and `low` during 0-bits."""
    e = str(low if bits[-1] == '0' else high)
    for i in range(len(bits) - 2, -1, -1): e = f'where(x < {i + 1}, {high if bits[i] == "1" else low}, {e})'
    return e


def waveform(spec, out):
    """spec: {"type": "AM" | "DSB-SC" | "FM" | "PM" | "ASK" | "FSK" | "PSK", "mu": 0.5 or [0.5, 1, 1.5] (AM: one panel
              each), "beta": 5 (FM/PM), "fm": 1, "fc": 12 (illustrative: 10 to 20 times fm), "cycles": 2 (of the message),
              "bits": "10110" (ASK/FSK/PSK), "f1": 6, "f2": 12 (FSK, cycles per bit), "Ac": 1, "time_unit": "ms"}
    Message, carrier and modulated wave as stacked panels on one time axis, computed; AM shows its envelope dashed (and
    over-modulation for μ > 1); DSB-SC shows the phase reversals; digital schemes show the bit train above the waveform.
    Frequencies are illustrative (the figure says "not to scale"); the numbers of the example go in the text."""
    t = str(spec.get('type', 'AM')).upper().replace('_', '-')
    fm, fc, Ac = float(spec.get('fm', 1)), float(spec.get('fc', 12)), float(spec.get('Ac', 1))
    T = float(spec.get('cycles', 2)) / fm
    rng, tu = [0, T], spec.get('time_unit', 'ms')
    m, c = f'cos(2*pi*{fm}*x)', f'cos(2*pi*{fc}*x)'
    panels = []
    if t in ('AM', 'DSB-SC', 'FM', 'PM'):
        panels += [{'ylabel': 'm(t)', 'curves': [{'expr': m, 'range': rng}]}, {'ylabel': 'c(t)', 'curves': [{'expr': f'{Ac}*{c}', 'range': rng}]}]
        if t == 'AM':
            for mu in (spec.get('mu', 0.5) if isinstance(spec.get('mu'), list) else [spec.get('mu', 0.5)]):
                mu = float(mu); env = f'{Ac}*(1 + {mu}*{m})'
                panels.append({'ylabel': 's(t)', 'title': f'μ = {_fmt(mu)}' + (' (over-modulated)' if mu > 1 else ''),
                               'curves': [{'expr': f'{env}*{c}', 'range': rng, 'label': 'AM wave'},
                                          {'expr': env, 'range': rng, 'style': '--', 'label': 'envelope', 'color': 'gold'},
                                          {'expr': f'-({env})', 'range': rng, 'style': '--', 'label': 'envelope', 'color': 'gold'}]})
        elif t == 'DSB-SC':
            panels.append({'ylabel': 's(t)', 'curves': [{'expr': f'{Ac}*{m}*{c}', 'range': rng, 'label': 'DSB-SC wave'},
                                                       {'expr': f'{Ac}*abs({m})', 'range': rng, 'style': '--', 'label': '|m(t)|', 'color': 'gold'},
                                                       {'expr': f'-{Ac}*abs({m})', 'range': rng, 'style': '--', 'label': '|m(t)|', 'color': 'gold'}]})
        else:
            beta = float(spec.get('beta', 5))
            phase = f'{beta}*sin(2*pi*{fm}*x)' if t == 'FM' else f'{beta}*{m}'
            panels.append({'ylabel': 's(t)', 'curves': [{'expr': f'{Ac}*cos(2*pi*{fc}*x + {phase})', 'range': rng, 'label': f'{t} wave, β = {_fmt(beta)}'}]})
    elif t in ('ASK', 'OOK', 'FSK', 'PSK', 'BPSK'):
        bits = re.sub(r'[^01]', '', str(spec.get('bits', '10110'))) or '1'
        rng, f1, f2 = [0, len(bits)], float(spec.get('f1', 3)), float(spec.get('f2', 6))
        panels.append({'ylabel': 'data', 'curves': [{'x': list(range(len(bits) + 1)), 'y': [int(b) for b in bits] + [int(bits[-1])], 'step': True}],
                       'ylim': [-0.3, 1.4], 'yticks': [0, 1]})
        carrier = f'cos(2*pi*{f2}*x)'
        if t in ('ASK', 'OOK'): wave = f'{_bits_expr(bits, Ac, 0)}*{carrier}'
        elif t == 'FSK': wave = f'{Ac}*cos(2*pi*{_bits_expr(bits, f2, f1)}*x)'
        else: wave = f'{Ac}*{_bits_expr(bits, 1, -1)}*{carrier}'
        panels.append({'ylabel': f'{t} s(t)', 'curves': [{'expr': wave, 'range': rng}]})
        tu = 'bit periods'
    else: raise ValueError(f'unknown waveform type {t!r}; use AM, DSB-SC, FM, PM, ASK, FSK or PSK')
    ps, plot = _plot({'panels': panels, 'xlabel': f't ({tu}), not to scale', 'size': [6.4, 1.25 * len(panels) + 0.4]})
    return plot(ps, out)


def spectrum(spec, out):
    """spec: {"type": "AM" | "DSB-SC" | "SSB" | "lines", "fc": 100, "fm": 5 or [5, 8], "Ac": 10, "mu": 0.5 or [0.5, 0.3],
              "unit": "kHz", "lines": [{"f": 95, "a": 2.5, "label": "μAc/2"}] (type "lines")}
    The one-sided amplitude spectrum as labelled spectral lines, computed: AM has the carrier Ac at fc and μAc/2 at
    fc ± fm (each tone of a multi-tone message), DSB-SC only the sidebands, SSB the upper sideband; the bandwidth is
    marked. Use for every spectrum of a modulated signal."""
    t = str(spec.get('type', 'AM')).upper()
    fc, Ac, u = float(spec.get('fc', 100)), float(spec.get('Ac', 1)), spec.get('unit', 'kHz')
    fms = [float(f) for f in (spec.get('fm') if isinstance(spec.get('fm'), list) else [spec.get('fm', 5)])]
    mus = [float(m) for m in (spec.get('mu') if isinstance(spec.get('mu'), list) else [spec.get('mu', 0.5)] * len(fms))]
    lines = [(float(l['f']), float(l['a']), l.get('label', '')) for l in spec.get('lines', [])] if t == 'LINES' else []
    if t in ('AM', 'DSB-SC', 'SSB'):
        if t == 'AM': lines.append((fc, Ac, f'Ac = {_fmt(Ac)}'))
        for fm, mu in zip(fms, mus):
            a = mu * Ac / 2 if t == 'AM' else Ac / 2
            if t != 'SSB': lines.append((fc - fm, a, f'{_fmt(round(a, 3))}'))
            lines.append((fc + fm, a, f'{_fmt(round(a, 3))}'))
    if not lines: raise ValueError('a spectrum needs "type" AM, DSB-SC or SSB with fc and fm, or "lines"')
    fs = [f for f, _, _ in lines]; top = max(a for _, a, _ in lines)
    span = max(max(fs) - min(fs), 1e-9)
    bw = (max(fs) - min(fs)) if t != 'AM' or len(lines) > 1 else 0
    hl = [{'y': 0}]
    ps, plot = _plot({'xlabel': f'f ({u})', 'ylabel': 'amplitude', 'size': [6.0, 2.8], 'legend': False, 'xticks': sorted(set(fs)),
                      'xlim': [min(fs) - 0.25 * span, max(fs) + 0.25 * span], 'ylim': [0, 1.45 * top],
                      'curves': [{'x': [f for f, _, _ in lines], 'y': [a for _, a, _ in lines], 'stem': True}],
                      'points': [{'x': f, 'y': a, 'label': lab} for f, a, lab in lines if lab],
                      'annotations': [{'xy': [min(fs) + span / 2, 1.3 * top], 'text': f'bandwidth B = {_fmt(round(bw, 4))} {u}'}] if bw else [],
                      'hlines': hl})
    return plot(ps, out)


# ---------------------------------------------------------------- thermodynamic cycles
CP_FLUIDS = {'water': 'Water', 'steam': 'Water', 'r134a': 'R134a', 'ammonia': 'Ammonia', 'r717': 'Ammonia', 'r22': 'R22', 'co2': 'CO2', 'r744': 'CO2'}


def _ideal_states(spec):
    R, gamma = float(spec.get('R', 0.287)), float(spec.get('gamma', 1.4))
    st = {}
    for s in spec['states']:
        p, v, T = (float(s[k]) if s.get(k) is not None else None for k in ('p', 'v', 'T'))
        if p is None: p = R * T / v
        if v is None: v = R * T / p
        if T is None: T = p * v / R
        st[str(s['name'])] = {'p': p, 'v': v, 'T': T}
    s0 = next(iter(st.values()))
    cp = R * gamma / (gamma - 1)
    for s in st.values(): s['s'] = cp * np.log(s['T'] / s0['T']) - R * np.log(s['p'] / s0['p'])
    return st, R, gamma, cp, s0


def _ideal_path(a, b, kind, n, R, gamma, cp, s0):
    """Points (p, v, T, s) along one ideal-gas process from state a to b."""
    if kind == 'isochoric': v = np.full(80, a['v']); p = np.linspace(a['p'], b['p'], 80)
    elif kind == 'isobaric': p = np.full(80, a['p']); v = np.linspace(a['v'], b['v'], 80)
    else:
        if kind == 'isothermal': n = 1.0
        elif kind == 'isentropic': n = gamma
        elif n is None: n = np.log(b['p'] / a['p']) / np.log(a['v'] / b['v'])        # polytropic through both end states
        v = np.geomspace(a['v'], b['v'], 120); p = a['p'] * (a['v'] / v) ** n
    T = p * v / R
    return p, v, T, cp * np.log(T / s0['T']) - R * np.log(p / s0['p'])


def cycle(spec, out):
    """spec: {"fluid": "air" (ideal gas) | "water" | "R134a" | "ammonia", "diagram": "pv" | "ts" | "ph",
              "states": [{"name": "1", "p": 100, "T": 300}, ...]   (p in kPa, T in K, v in m³/kg; ideal gas: any two of p, v, T;
                         real fluids: two of p, T, x (quality 0-1), h (kJ/kg), s (kJ/kg·K)),
              "processes": [{"from": "1", "to": "2", "type": "isentropic" | "isothermal" | "isobaric" | "isochoric" |
                             "polytropic" | "throttling", "n": 1.3}],
              "gamma": 1.4, "R": 0.287 (ideal gas, kJ/kg·K)}
    The cycle drawn with true process curves: pvⁿ = constant, isentropes vertical on T-s, isobars curving on T-s; for steam
    and refrigerants the saturation dome and the states come from real fluid properties (CoolProp). States are numbered,
    each process has a direction arrow. Use for Otto, Diesel, Brayton, Carnot, Rankine and vapour-compression cycles."""
    brand()
    fluid = str(spec.get('fluid', 'air')).lower()
    diag = str(spec.get('diagram', 'ts')).lower().replace('-', '')
    fig, ax = plt.subplots(figsize=(5.6, 4.0)); notes = []
    axes_of = {'pv': ('v', 'p', 'v (m³/kg)', 'p (kPa)'), 'ts': ('s', 'T', 's (kJ/kg·K)', 'T (K)'), 'ph': ('h', 'p', 'h (kJ/kg)', 'p (kPa)')}
    if diag not in axes_of: raise ValueError('diagram must be "pv", "ts" or "ph"')
    xk, yk, xl, yl = axes_of[diag]
    if fluid in CP_FLUIDS:
        st, paths = _real_cycle(spec, CP_FLUIDS[fluid], ax, diag)
    else:
        if diag == 'ph': raise ValueError('a p-h diagram needs a real fluid (water, R134a, ammonia)')
        st, R, gamma, cp, s0 = _ideal_states(spec)
        paths = []
        for pr in spec.get('processes', []):
            p, v, T, s = _ideal_path(st[str(pr['from'])], st[str(pr['to'])], pr.get('type', 'polytropic'), pr.get('n'), R, gamma, cp, s0)
            paths.append({'p': p, 'v': v, 'T': T, 's': s})
    for k, (pr, pth) in enumerate(zip(spec.get('processes', []), paths)):
        X, Y = pth[xk], pth[yk]
        ax.plot(X, Y, color=PURPLE, lw=1.9, ls='--' if pr.get('type') == 'throttling' else '-')
        i = len(X) // 2
        ax.add_patch(FancyArrowPatch((X[i - 1], Y[i - 1]), (X[i], Y[i]), arrowstyle='-|>', mutation_scale=12, color=PURPLE, lw=0))
    for name, s in st.items():
        ax.plot(s[xk], s[yk], 'o', color=GOLD, ms=6, zorder=5)
        notes.append(ax.annotate(name, (s[xk], s[yk]), textcoords='offset points', xytext=(6, 6), fontsize=10, color=PURPLE, fontweight='bold'))
    if diag == 'pv' and fluid in CP_FLUIDS: ax.set_xscale('log')
    if diag == 'ph': ax.set_yscale('log')
    ax.set_xlabel(xl); ax.set_ylabel(yl)
    ISSUES.append(LBL.place(fig, ax, notes))
    return save(fig, out)


def _real_cycle(spec, name, ax, diag):
    """States, process paths and the saturation dome of a real fluid (CoolProp, SI units converted to kPa, kJ)."""
    try: import CoolProp.CoolProp as CP
    except ImportError: raise ValueError('real-fluid cycles need CoolProp, which is not installed')
    P = lambda out, *a: CP.PropsSI(out, *a, name)
    conv = {'p': ('P', 1000), 'T': ('T', 1), 'x': ('Q', 1), 'h': ('H', 1000), 's': ('S', 1000)}
    st = {}
    for s in spec['states']:
        given = [(conv[k][0], float(s[k]) * conv[k][1]) for k in ('p', 'T', 'x', 'h', 's') if s.get(k) is not None][:2]
        if len(given) < 2: raise ValueError(f'state {s.get("name")} needs two of p, T, x, h, s')
        args = [v for g in given for v in g]
        try: P('P', *args)
        except ValueError:              # (T, h) and (T, s) are not input pairs: a two-phase state, so T fixes the pressure
            if given[0][0] != 'T' and given[1][0] != 'T': raise
            T = dict(given)['T']; other = [g for g in given if g[0] != 'T'][0]
            args = ['P', P('P', 'T', T, 'Q', 0), *other]
        st[str(s['name'])] = {'p': P('P', *args) / 1000, 'T': P('T', *args), 'h': P('H', *args) / 1000, 's': P('S', *args) / 1000, 'v': 1 / P('D', *args)}
    paths = []
    for pr in spec.get('processes', []):
        a, b = st[str(pr['from'])], st[str(pr['to'])]
        kind = pr.get('type', 'isobaric')
        if kind == 'isentropic': pts = [('P', p * 1000, 'S', a['s'] * 1000) for p in np.geomspace(a['p'], b['p'], 60)]
        elif kind in ('isobaric', 'isothermal'): pts = [('P', a['p'] * 1000, 'H', h * 1000) for h in np.linspace(a['h'], b['h'], 120)]
        elif kind == 'throttling': pts = [('H', a['h'] * 1000, 'P', p * 1000) for p in np.geomspace(a['p'], b['p'], 60)]
        else: raise ValueError(f'process type {kind!r} is not drawn for real fluids; use isentropic, isobaric or throttling')
        pth = {k: [] for k in 'pThsv'}
        for args in pts:
            pth['p'].append(P('P', *args) / 1000); pth['T'].append(P('T', *args)); pth['h'].append(P('H', *args) / 1000)
            pth['s'].append(P('S', *args) / 1000); pth['v'].append(1 / P('D', *args))
        paths.append({k: np.array(v) for k, v in pth.items()})
    Tc, Tt = CP.PropsSI('Tcrit', name), CP.PropsSI('Ttriple', name)
    Ts = np.linspace(max(Tt + 0.5, 0.55 * Tc), Tc - 0.05, 160)
    dome = {k: [] for k in 'pThsv'}
    for q in (0, 1):
        for T in (Ts if q == 0 else Ts[::-1]):
            dome['T'].append(T); dome['p'].append(P('P', 'T', T, 'Q', q) / 1000); dome['h'].append(P('H', 'T', T, 'Q', q) / 1000)
            dome['s'].append(P('S', 'T', T, 'Q', q) / 1000); dome['v'].append(1 / P('D', 'T', T, 'Q', q))
    xk, yk = {'pv': ('v', 'p'), 'ts': ('s', 'T'), 'ph': ('h', 'p')}[diag]
    ax.plot(dome[xk], dome[yk], color=GREY, lw=1, ls='--', label='saturation dome')
    return st, paths


# ---------------------------------------------------------------- control systems
def control(spec, out):
    """spec: {"num": [10], "den": [1, 2, 10] (coefficients of G(s), highest power first), "plot": "step" | "bode" |
              "nyquist" | "rootlocus", "time": 6 (step: seconds), "feedback": true (step: unity negative feedback around G)}
    Computed responses: the step response with peak overshoot Mp, peak time tp, settling time ts (2 %) and the final value
    marked; the Bode magnitude and phase with the gain and phase crossover and margins; the Nyquist plot with (−1, 0); the
    root locus (K from 0 upward) with poles × and zeros ○. Use for every response plot of a transfer function."""
    from scipy import signal
    num, den = [float(c) for c in spec['num']], [float(c) for c in spec['den']]
    kind = spec.get('plot', 'step')
    if kind == 'step':
        if spec.get('feedback'): den = list(np.polyadd(den, num))
        t, y = signal.step(signal.lti(num, den), T=np.linspace(0, float(spec.get('time', 10)), 2000))
        fv = float(np.polyval(num, 0) / np.polyval(den, 0)) if np.polyval(den, 0) else float(y[-1])
        i = int(np.argmax(y)); mp = (y[i] - fv) / fv * 100 if fv else 0
        out_band = np.where(np.abs(y - fv) > 0.02 * abs(fv))[0]
        ts = t[out_band[-1] + 1] if len(out_band) and out_band[-1] + 1 < len(t) else None
        pts = [{'x': float(t[i]), 'y': float(y[i]), 'label': f'Mp = {_fmt(round(mp, 1))} %, tp = {_fmt(round(t[i], 3))} s'}] if mp > 0.5 else []
        ps, plot = _plot({'xlabel': 't (s)', 'ylabel': 'c(t)', 'legend': False, 'curves': [{'x': list(t), 'y': list(y)}],
                          'hlines': [{'y': fv, 'label': f'final value {_fmt(round(fv, 3))}'}], 'points': pts,
                          'vlines': [{'x': float(ts), 'label': f'ts = {_fmt(round(ts, 2))} s (2 %)'}] if ts else []})
        return plot(ps, out)
    w = np.logspace(-2, 3, 1500)
    w, H = signal.freqs(num, den, worN=w)
    if kind == 'bode':
        mag, ph = 20 * np.log10(np.abs(H)), np.degrees(np.unwrap(np.angle(H)))
        notes_m, notes_p = [], []
        gc = np.where(np.diff(np.sign(mag)))[0]
        if len(gc): notes_m.append({'x': float(w[gc[0]]), 'y': 0, 'label': f'ωgc = {_fmt(round(w[gc[0]], 3))} rad/s, PM = {_fmt(round(180 + ph[gc[0]], 1))}°'})
        pc = np.where(np.diff(np.sign(ph + 180)))[0]
        if len(pc): notes_p.append({'x': float(w[pc[0]]), 'y': -180, 'label': f'ωpc = {_fmt(round(w[pc[0]], 3))} rad/s, GM = {_fmt(round(-mag[pc[0]], 1))} dB'})
        ps, plot = _plot({'xlabel': 'ω (rad/s)', 'logx': True, 'size': [6.2, 4.0],
                          'panels': [{'ylabel': '|G| (dB)', 'grid': True, 'curves': [{'x': list(w), 'y': list(mag)}], 'hlines': [0], 'points': notes_m},
                                     {'ylabel': '∠G (deg)', 'grid': True, 'curves': [{'x': list(w), 'y': list(ph)}], 'hlines': [-180], 'points': notes_p}]})
        return plot(ps, out)
    if kind == 'nyquist':
        ps, plot = _plot({'xlabel': 'Re G(jω)', 'ylabel': 'Im G(jω)', 'equal': True, 'axes_at_zero': True, 'legend': False,
                          'curves': [{'x': list(H.real), 'y': list(H.imag), 'label': 'ω > 0'}, {'x': list(H.real), 'y': list(-H.imag), 'style': '--', 'label': 'ω < 0'}],
                          'points': [{'x': -1, 'y': 0, 'label': '(−1, 0)', 'color': 'red'}]})
        return plot(ps, out)
    if kind == 'rootlocus':
        Ks = np.concatenate([[0], np.logspace(-3, 4, 1500)])
        roots = np.array([np.sort_complex(np.roots(np.polyadd(den, K * np.array(num)))) for K in Ks])
        reach = 3 * max([1.0] + [abs(r) for r in np.roots(den)] + [abs(r) for r in (np.roots(num) if len(num) > 1 else [])])
        roots[np.abs(roots) > reach] = np.nan          # branches leave along their asymptotes: the plot stays near the poles
        curves = [{'x': list(roots[:, j].real), 'y': list(roots[:, j].imag), 'color': PALETTE[j % len(PALETTE)], 'lw': 1.6} for j in range(roots.shape[1])]
        poles, zeros = np.roots(den), np.roots(num) if len(num) > 1 else []
        ps, plot = _plot({'xlabel': 'σ', 'ylabel': 'jω', 'axes_at_zero': True, 'legend': False, 'curves': curves,
                          'points': [{'x': float(p.real), 'y': float(p.imag), 'marker': 'x', 'color': 'red'} for p in poles] +
                                    [{'x': float(z.real), 'y': float(z.imag), 'marker': 'o', 'mfc': 'none', 'color': 'red'} for z in zeros]})
        return plot(ps, out)
    raise ValueError('plot must be "step", "bode", "nyquist" or "rootlocus"')


# ---------------------------------------------------------------- McCabe-Thiele and vapour-liquid equilibrium
def mccabe(spec, out):
    """spec: {"alpha": 2.5 (constant relative volatility of the more volatile component) | "eq": {"x": [...], "y": [...]} (a table),
              "xD": 0.95, "xF": 0.5, "xB": 0.05 (mole fractions of the more volatile component), "q": 1 (feed condition:
              1 saturated liquid, 0 saturated vapour; default 1), "R": 2.0 (external reflux ratio, above the minimum)}
    The McCabe-Thiele diagram, computed: equilibrium curve, diagonal, rectifying line, q-line and stripping line, and the
    staircase of equilibrium stages from xD to xB, numbered, with the feed stage marked. The title gives the stage count
    (a total condenser is not counted; the partial reboiler is the last stage). A reflux below the minimum is an error.
    Use it for every stage-count question; take the stage count and the feed stage in your text from the same inputs."""
    s = mccabe_solution(spec)
    yeq = equilibrium(spec)[0]; xx = np.linspace(0, 1, 201)
    xD, xB, xF = (float(spec[k]) for k in ('xD', 'xB', 'xF'))
    curves = [{'x': list(xx), 'y': list(yeq(xx)), 'label': 'Equilibrium curve', 'color': PURPLE},
              {'x': [0, 1], 'y': [0, 1], 'label': 'y = x', 'style': '--', 'color': GREY, 'lw': 1.2},
              {'x': [s['xi'], xD], 'y': [s['yi'], xD], 'label': 'Rectifying line', 'color': GOLD},
              {'x': [xB, s['xi']], 'y': [xB, s['yi']], 'label': 'Stripping line', 'color': TEAL},
              {'x': [xF, s['xi']], 'y': [xF, s['yi']], 'label': 'q-line', 'style': ':', 'color': PINK},
              {'x': s['x'], 'y': s['y'], 'label': 'Stages', 'color': '#7B5CB8', 'lw': 1.4}]
    corners = [(x, y) for x, y in zip(s['x'][1::2], s['y'][1::2])]               # where each stage meets the equilibrium curve
    points = [{'x': v, 'y': v, 'label': f'{n} = {v:g}'} for n, v in (('xD', xD), ('xF', xF), ('xB', xB))]
    if s['N'] <= 12: points += [{'x': x, 'y': y, 'label': str(k)} for k, (x, y) in enumerate(corners, 1)]
    ps, plot = _plot({'size': [5.4, 5.4], 'equal': True, 'xlim': [0, 1], 'ylim': [0, 1], 'xlabel': spec.get('xlabel', 'x (liquid mole fraction)'),
                      'ylabel': spec.get('ylabel', 'y (vapour mole fraction)'), 'curves': curves, 'points': points,
                      'title': f"N = {s['N']} stages, feed on stage {s['feed']}"})
    return plot(ps, out)


def vle(spec, out):
    """spec: {"components": [{"name": "Benzene", "antoine": [6.90565, 1211.033, 220.79]}, {"name": "Toluene", "antoine": [6.95464, 1344.8, 219.482]}]
                 (Antoine constants A, B, C for log10 of the pressure in mmHg and the temperature in degC; either order, the one that boils
                 first is plotted as "x" and "y"),
              "P": 760 (total pressure, mmHg), "diagram": "txy" (bubble and dew curves against composition, default) | "xy"
                 (equilibrium curve with the diagonal), "tie": 0.4 (optional liquid mole fraction: a tie line on the Txy diagram with its
                 x, y and T marked)}
    Computed vapour-liquid equilibrium of an ideal binary mixture at constant pressure. Use it for every Txy and xy diagram of a binary
    (boiling-point diagrams, flash and distillation notes); the pure boiling points and the mean relative volatility are marked."""
    s = antoine_vle(spec)
    name, other = s['names']
    label = f'{name} mole fraction'
    if spec.get('diagram', 'txy') == 'xy':
        ps, plot = _plot({'size': [4.6, 4.6], 'equal': True, 'xlim': [0, 1], 'ylim': [0, 1], 'xlabel': f'x ({label}, liquid)', 'ylabel': f'y ({label}, vapour)',
                          'curves': [{'x': list(s['x']), 'y': list(s['y']), 'label': 'Equilibrium curve', 'color': PURPLE},
                                     {'x': [0, 1], 'y': [0, 1], 'label': 'y = x', 'style': '--', 'color': GREY, 'lw': 1.2}],
                          'title': f"Mean relative volatility α ≈ {s['alpha']:.2f}"})
        return plot(ps, out)
    curves = [{'x': list(s['x']), 'y': list(s['T']), 'label': 'Bubble-point curve (liquid)', 'color': PURPLE},
              {'x': list(s['y']), 'y': list(s['T']), 'label': 'Dew-point curve (vapour)', 'color': GOLD}]
    points = [{'x': 0, 'y': s['Tb'][1], 'label': f"{other} {s['Tb'][1]:.1f} °C", 'offset': (10, 8)}, {'x': 1, 'y': s['Tb'][0], 'label': f"{name} {s['Tb'][0]:.1f} °C", 'offset': (-84, -16)}]
    if s.get('tie'):
        t = s['tie']
        curves.append({'x': [t['x'], t['y']], 'y': [t['T'], t['T']], 'label': 'Tie line', 'style': '--', 'color': TEAL, 'lw': 1.6})
        points += [{'x': t['x'], 'y': t['T'], 'label': f"x = {t['x']:.2f}", 'offset': (-48, -14)}, {'x': t['y'], 'y': t['T'], 'label': f"y = {t['y']:.2f}", 'offset': (6, 8)}]
    ps, plot = _plot({'size': [5.6, 3.8], 'xlim': [0, 1], 'ylim': [s['Tb'][0] - 5, s['Tb'][1] + 4], 'xlabel': f'x, y ({label})', 'ylabel': 'Temperature (°C)', 'curves': curves, 'points': points,
                      'title': f"{spec.get('P', 760):g} mmHg"})
    return plot(ps, out)

"""The geometry figure kind: drawings with real positions and true proportions (equal axes always) - traverses and
bearings, plates with holes, free-body and force diagrams, trusses, velocity triangles, submerged and floating bodies
(upright or tilted), constellations. Its exact spec is the docstring of geometry(): figures.reference() gives it to the
model."""
import numpy as np
import matplotlib.colors
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Arc, FancyArrowPatch, PathPatch
from matplotlib.path import Path
from figstyle import PURPLE, INK, GREY, PALETTE, ISSUES, col, brand, save, _size
import labels as LBL


def _rot(pts, deg, about):
    """Points rotated by deg (counter-clockwise) about a point."""
    if not deg: return np.asarray(pts, float)
    a = np.radians(float(deg)); c, s = np.cos(a), np.sin(a)
    p = np.asarray(pts, float) - about
    return p @ np.array([[c, s], [-s, c]]) + about


def _shape_points(it):
    t = it['type']
    if t == 'rect':
        x, y = it.get('at', [0, 0]); w, h = float(it['w']), float(it['h'])
        pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    else: pts = it['points']
    about = np.asarray(it.get('about', np.mean(np.asarray(pts, float), axis=0)), float)
    return _rot(pts, it.get('rotate', 0), about)


def geometry(spec, out):
    """spec: {"items": [ITEM, ...], "axes": false (schematic, no axes) | true (coordinate grid with "xlabel", "ylabel"),
              "depth_down": bool (the y values are depths: drawn growing downward, e.g. submerged plates),
              "north": true (a north arrow in the corner), "size": [w, h] inches, "title"}
    ITEM types (coordinates in one unit system; labels are placed clear of other labels and lines automatically):
      {"type": "point", "at": [x, y], "label": "G", "color"}
      {"type": "segment", "from": [x, y], "to": [x, y], "label": "100 m", "style": "-"|"--"|":", "color", "lw"}
      {"type": "arrow", "from": [x, y], "to": [x, y], "label": "F_B = 1962 N", "color"}          (a force or vector)
      {"type": "polygon", "points": [[x, y], ...], "fill": "lav"|colour|null, "holes": [[[x, y], ...]], "label",
                          "rotate": deg (counter-clockwise), "about": [x, y]}                          (a body, a plate, a tank)
      {"type": "rect", "at": [x, y] (lower left), "w", "h", "fill", "label", "rotate", "about"}
      {"type": "circle", "center": [x, y], "r", "fill": null|colour, "label"}                       (a hole, a pulley, a node)
      {"type": "angle", "center": [x, y], "from_deg", "to_deg", "r", "label": "θ = 30°"}              (an angle arc, degrees from +x,
                                                                                                      counted in the spec's own x, y: with depth_down, +y is deeper)
      {"type": "dim", "from": [x, y], "to": [x, y], "label": "2.4 m", "offset": 0.3}                  (a dimension line beside a length)
      {"type": "bearing", "from": [x, y], "bearing": deg (clockwise from north), "length", "label": "P1: 100 m, 030°", "to_label": "B"}
      {"type": "surface", "y": 0, "x": [x1, x2], "label": "free surface"}                            (water level: line and ▽)
      {"type": "ground", "from": [x, y], "to": [x, y]}                                               (hatched support or ground)
      {"type": "text", "at": [x, y], "text": "..."}
    Use for anything whose shape and position matter: traverses (bearing items), a plate with a hole (polygon + circle,
    with the centroids as points), a floating body tilted by θ (polygon with "rotate", and G, B, B′, M as points with the
    weight and buoyancy as arrows), a gate with its depth (depth_down), free-body diagrams, trusses, velocity triangles."""
    brand()
    fig, ax = plt.subplots(figsize=_size(spec))
    notes, k, shapes = [], 0, []
    flip = -1 if spec.get('depth_down') else 1
    def label(text, xy, offset=(6, 6), size=8.5, color=INK, prefer=()):
        if not text: return
        notes.append(ax.annotate(str(text), tuple(map(float, xy)), textcoords='offset points', xytext=offset, fontsize=size, color=color))
        notes[-1].prefer = prefer
    def beside(a, b, first=None):
        """Offsets (points) to either side of a line from a to b, nearest first; `first` is the side tried first."""
        d = (b - a) * [1, flip]; n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) or 1)
        if first is not None and np.dot(n, np.asarray(first, float) * [1, flip]) < 0: n = -n
        return [tuple(np.round(sgn * n * r, 1)) for r in (7, 14, 24, 36) for sgn in (1, -1)]
    for it in spec.get('items', []):
        t = it.get('type')
        c = col(it.get('color'), PURPLE)
        if t == 'point':
            ax.plot(*it['at'], 'o', color=c, ms=5, zorder=6); label(it.get('label'), it['at'], size=9, color=PURPLE)
        elif t in ('segment', 'arrow'):
            a, b = np.asarray(it['from'], float), np.asarray(it['to'], float)
            if t == 'segment': ax.plot(*zip(a, b), ls=it.get('style', '-'), color=c, lw=it.get('lw', 1.6))
            else: ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=14, color=col(it.get('color'), PALETTE[2]), lw=2, zorder=5))
            label(it.get('label'), (a + b) / 2, beside(a, b)[0], prefer=beside(a, b))
        elif t in ('polygon', 'rect'):
            pts = _shape_points(it)
            verts, codes = list(pts) + [pts[0]], [Path.MOVETO] + [Path.LINETO] * (len(pts) - 1) + [Path.CLOSEPOLY]
            for hole in it.get('holes', []):
                h = _rot(hole, it.get('rotate', 0), np.asarray(it.get('about', np.mean(pts, axis=0)), float))[::-1]
                verts += list(h) + [h[0]]; codes += [Path.MOVETO] + [Path.LINETO] * (len(h) - 1) + [Path.CLOSEPOLY]
            fill = it.get('fill', 'lav')
            ax.add_patch(PathPatch(Path(verts, codes), facecolor=(*matplotlib.colors.to_rgb(col(fill)), 0.45) if fill else 'none',
                                   edgecolor=c, lw=1.6, zorder=2))        # translucent: where shapes overlap, the overlap shows
            if it.get('label'):                         # inside its own shape: the centre, else towards a corner
                m = pts.mean(axis=0)
                notes.append(ax.annotate(str(it['label']), tuple(m), xytext=tuple(m), fontsize=8.5, color=INK, ha='center', va='center'))
                notes[-1].spots = [m + f * (v - m) for f in (0.5, 0.7) for v in pts] + [m + 0.6 * ((u + v) / 2 - m) for u, v in zip(pts, np.roll(pts, 1, axis=0))]
                shapes.append((notes[-1], Path(verts, codes)))
        elif t == 'circle':
            fill = it.get('fill')
            ax.add_patch(Circle(it['center'], float(it['r']), facecolor=col(fill) if fill else 'white', edgecolor=c, lw=1.6, zorder=3))
            label(it.get('label'), it['center'], (6, 6))
        elif t == 'angle':
            r = float(it.get('r', 1))
            ax.add_patch(Arc(it['center'], 2 * r, 2 * r, theta1=float(it['from_deg']), theta2=float(it['to_deg']), color=GREY, lw=1))
            mid = np.radians((float(it['from_deg']) + float(it['to_deg'])) / 2)
            label(it.get('label'), np.asarray(it['center'], float) + 1.15 * r * np.array([np.cos(mid), np.sin(mid)]), (2, 0))
        elif t == 'dim':
            a, b = np.asarray(it['from'], float), np.asarray(it['to'], float)
            n = np.array([-(b - a)[1], (b - a)[0]]); n = n / (np.linalg.norm(n) or 1) * float(it.get('offset', 0))
            ax.annotate('', a + n, xytext=b + n, arrowprops=dict(arrowstyle='<->', color=GREY, lw=0.9))
            for p in (a, b): ax.plot(*zip(p, p + 1.15 * n), color=GREY, lw=0.6)
            side = beside(a, b, n if np.any(n) else None)
            label(it.get('label'), (a + b) / 2 + n, side[0], 8, INK, prefer=side)
        elif t == 'bearing':
            a = np.asarray(it['from'], float); th = np.radians(float(it['bearing']))
            b = a + float(it.get('length', 1)) * np.array([np.sin(th), np.cos(th)])          # clockwise from north
            ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=14, color=PALETTE[(k := k + 1) % len(PALETTE)], lw=1.8, zorder=4))
            label(it.get('label'), (a + b) / 2, beside(a, b)[0], prefer=beside(a, b))
            if it.get('to_label'): ax.plot(*b, 'o', color=PURPLE, ms=4, zorder=6); label(it['to_label'], b, (5, 5), 9, PURPLE)
        elif t == 'surface':
            x1, x2 = it.get('x', [None, None]); y = float(it.get('y', 0))
            ax.axhline(y, color='#2E8B87', lw=1.2) if x1 is None else ax.plot([x1, x2], [y, y], color='#2E8B87', lw=1.2)
            xm = (x1 + x2) / 2 if x1 is not None else None
            if xm is not None: ax.plot(xm, y, marker='v', color='#2E8B87', ms=7, zorder=5)
            label(it.get('label'), (x2 if x2 is not None else 0, y), (4, 4), 8, '#2E8B87')
        elif t == 'ground':
            a, b = np.asarray(it['from'], float), np.asarray(it['to'], float)
            ax.plot(*zip(a, b), color=INK, lw=1.4)
            L = np.linalg.norm(b - a); u = (b - a) / (L or 1); n = np.array([u[1], -u[0]]) * L * 0.04
            for s in np.linspace(0, 1, max(int(L / (L * 0.06)), 4)): p = a + s * (b - a); ax.plot(*zip(p, p + n - u * L * 0.03), color=INK, lw=0.6)
        elif t == 'text':
            label(it.get('text'), it['at'], (0, 0), 8.5, INK)
        else: raise ValueError(f'unknown geometry item type {t!r}')
    ax.set_aspect('equal', adjustable='datalim')
    ax.autoscale_view()
    if spec.get('depth_down'): ax.invert_yaxis()
    if spec.get('axes'):
        ax.grid(True, lw=0.5); ax.set_xlabel(spec.get('xlabel', '')); ax.set_ylabel(spec.get('ylabel', ''))
    else: ax.axis('off')
    if spec.get('north'):
        ax.annotate('N', xy=(0.04, 0.97), xytext=(0.04, 0.82), xycoords='axes fraction', ha='center', fontsize=9, color=INK,
                    arrowprops=dict(arrowstyle='-|>', color=INK, lw=1.2))
    if spec.get('title'): ax.set_title(spec['title'])
    ax.margins(0.08)
    for t, path in shapes:          # a shape's label goes where no other shape covers it, so it cannot be read as the other's
        spots = sorted([np.array(t.xy)] + t.spots, key=lambda q: sum(o.contains_point(q) for u, o in shapes if u is not t))
        t.xyann, t.spots = tuple(spots[0]), spots[1:]
    ISSUES.append(LBL.place(fig, ax, notes))
    return save(fig, out)

"""The process figure kind: a flowsheet of equipment (column, drum, heat exchanger, reactor, pump, vessel) joined by labelled
streams. The writer gives each piece of equipment a grid cell and says which stream joins which; the code draws the equipment,
routes every stream at right angles around the other equipment, and writes the labels on the streams, clear of everything.
Its exact spec is the docstring of process(): figures.reference() gives it to the model."""
import textwrap
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon
from figstyle import PURPLE, LAV, INK, ISSUES, brand, save
import labels as LBL

CELL_W, CELL_H, STUB, IN_PER_UNIT = 3.8, 2.5, 0.3, 0.62      # the widest column spacing, the row spacing, a stream's first stretch, inches per drawing unit
SIZES = {'column': (0.45, 0.95), 'drum': (0.7, 0.38), 'exchanger': (0.42, 0.42), 'reactor': (0.55, 0.75), 'pump': (0.32, 0.32)}   # half width, half height
ROUND = {'drum': 0.38, 'box': 0.06}                              # corner radius of the rounded symbols (the others: 0.18)
TYPES = sorted(list(SIZES) + ['vessel', 'box', 'terminal'])
NORMALS = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}
STREAM = '#6B6480'


def _draw_equipment(ax, kind, c, hw, hh):
    """The symbol of one piece of equipment, centred on c."""
    cx, cy = c
    style = dict(fc=LAV, ec=PURPLE, lw=1.6, zorder=3)
    if kind in ('exchanger', 'pump'): ax.add_patch(Circle(c, hw, **style))
    else: ax.add_patch(FancyBboxPatch((cx - hw, cy - hh), 2 * hw, 2 * hh, boxstyle=f'round,pad=0,rounding_size={ROUND.get(kind, 0.18)}', **style))
    line = dict(color=PURPLE, lw=1.1, zorder=4)
    if kind == 'column':
        for k in range(1, 7): ax.plot([cx - 0.7 * hw, cx + 0.7 * hw], [cy - hh + 2 * hh * k / 7] * 2, alpha=0.55, **line)       # the trays
    elif kind == 'exchanger':
        ax.plot(cx + hw * np.array([-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75]), cy + hw * np.array([0, 0.45, -0.45, 0.45, -0.45, 0.45, 0]), **line)
    elif kind == 'pump':
        ax.add_patch(Polygon([(cx - 0.45 * hw, cy - 0.5 * hw), (cx - 0.45 * hw, cy + 0.5 * hw), (cx + 0.6 * hw, cy)], closed=True, fc=PURPLE, ec=PURPLE, zorder=4))
    elif kind == 'reactor':
        ax.plot([cx, cx], [cy + hh, cy - 0.45 * hh], **line); ax.plot([cx - 0.45 * hw, cx + 0.45 * hw], [cy - 0.45 * hh] * 2, lw=2.2, color=PURPLE, zorder=4)   # the stirrer


def _hits(path, boxes, pad=0.1):
    """How many (segment, box) pairs of an axis-parallel path and boxes (x0, y0, x1, y1) overlap."""
    n = 0
    for (ax_, ay), (bx, by) in zip(path[:-1], path[1:]):
        lo, hi = (min(ax_, bx), min(ay, by)), (max(ax_, bx), max(ay, by))
        n += sum(lo[0] < x1 + pad and hi[0] > x0 - pad and lo[1] < y1 + pad and hi[1] > y0 - pad for x0, y0, x1, y1 in boxes)
    return n


def _crossings(path, others):
    """How many times a path crosses, or runs along, the streams already routed."""
    n = 0
    for (ax_, ay), (bx, by) in zip(path[:-1], path[1:]):
        for o in others:
            for (cx, cy), (dx, dy) in zip(o[:-1], o[1:]):
                horizontal = ay == by
                if horizontal != (cy == dy):                                     # at right angles: they cross when each passes through the other
                    h, v = ((ax_, ay, bx), (cx, cy, dy)) if horizontal else ((cx, cy, dx), (ax_, ay, by))
                    n += min(h[0], h[2]) < v[0] < max(h[0], h[2]) and min(v[1], v[2]) < h[1] < max(v[1], v[2])
                elif (horizontal and ay == cy and min(ax_, bx) < max(cx, dx) and max(ax_, bx) > min(cx, dx)) or \
                     (not horizontal and ax_ == cx and min(ay, by) < max(cy, dy) and max(ay, by) > min(cy, dy)):
                    n += 4                                                      # two streams on one line cannot be told apart
    return n


def _route(p0, n0, p1, n1, boxes, others, bounds):
    """An axis-parallel path from port p0 (leaving along n0) to port p1 (arriving against n1): the cheapest of several shapes
    (one or two bends, or round the outside of everything) that goes through no equipment."""
    a, b = (p0[0] + STUB * n0[0], p0[1] + STUB * n0[1]), (p1[0] + STUB * n1[0], p1[1] + STUB * n1[1])
    (x0, y0, x1, y1), mx, my = bounds, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    shapes = [[a, (b[0], a[1]), b], [a, (a[0], b[1]), b], [a, (mx, a[1]), (mx, b[1]), b], [a, (a[0], my), (b[0], my), b],
              [a, (a[0], y1), (b[0], y1), b], [a, (a[0], y0), (b[0], y0), b], [a, (x0, a[1]), (x0, b[1]), b], [a, (x1, a[1]), (x1, b[1]), b]]
    best = None
    for s in shapes:
        s = [s[0]] + [q for k, q in enumerate(s[1:], 1) if q != s[k - 1]]       # a corner on top of another point is no corner
        path = [p0] + s + [p1]
        cost = sum(abs(u[0] - v[0]) + abs(u[1] - v[1]) for u, v in zip(path[:-1], path[1:])) + 40 * _hits(s, boxes) + 6 * _crossings(path, others) + len(s)
        if best is None or cost < best[0]: best = (cost, path)
    return best[1]


def _runs(path):
    """A path as straight runs: consecutive segments along one line (a stub and the long stretch after it) are one run."""
    pts = [path[0]]
    for q in path[1:]:
        if len(pts) >= 2 and (pts[-2][0] == pts[-1][0] == q[0] or pts[-2][1] == pts[-1][1] == q[1]): pts[-1] = q
        else: pts.append(q)
    return list(zip(pts[:-1], pts[1:]))


def _label_spot(path, w, h, boxes, others):
    """Where a stream's label (w by h) goes, as (box, mode, point): "line" (on its own line, breaking it: the middle of the longest
    straight run that has room, the arrow head at the end needing some), else "beside" (just above or below such a run), else
    "lifted" (raised clear of the neighbouring equipment, to be joined to its stream by a short line). Always clear of the
    equipment, the other streams and the earlier labels. Returns (box, mode, the point of the stream the label belongs to), or (None, None, None)."""
    runs = sorted(_runs(path), key=lambda p: -(abs(p[0][0] - p[1][0]) + abs(p[0][1] - p[1][1])))
    free = lambda box: not _hits([(box[0], box[1]), (box[2], box[3])], boxes, 0.14) and not any(_hits(o, [box], 0.0) for o in others)
    for mode, lifts in (('line', [None]), ('beside', [0]), ('lifted', range(1, 8))):
        for u, v in runs:
            horizontal = u[1] == v[1]
            along, room = (w, abs(u[0] - v[0])) if horizontal else (h, abs(u[1] - v[1]))
            ends = v == path[-1]
            if mode == 'line' and room < along + 0.3 + 0.4 * ends: continue
            mx, my = (u[0] + v[0]) / 2, (u[1] + v[1]) / 2
            if ends and mode == 'line': mx, my = ((mx - 0.2 * (1 if v[0] > u[0] else -1), my) if horizontal else (mx, my - 0.2 * (1 if v[1] > u[1] else -1)))      # clear of the arrow head
            for lift in lifts:
                for side in ((0,) if lift is None else (1, -1)):
                    away = 0 if lift is None else side * ((h if horizontal else w) / 2 + 0.14 + 0.15 * lift)
                    cx, cy = (mx, my + away) if horizontal else (mx + away, my)
                    box = (cx - w / 2 - 0.07, cy - h / 2 - 0.05, cx + w / 2 + 0.07, cy + h / 2 + 0.05)
                    if free(box): return box, mode, (mx, my)
    return None, None, None


def _broken(path, box):
    """The pieces (u, v) of a path with the stretch under a label box left out."""
    pieces = []
    for u, v in zip(path[:-1], path[1:]):
        horizontal = u[1] == v[1]
        lo, hi = (box[0], box[2]) if horizontal else (box[1], box[3])
        a, b = (u[0], v[0]) if horizontal else (u[1], v[1])
        if not ((box[1] < u[1] < box[3] if horizontal else box[0] < u[0] < box[2]) and min(a, b) < hi and max(a, b) > lo):
            pieces.append((u, v)); continue
        sign = 1 if b > a else -1
        enter, leave = (lo, hi) if sign > 0 else (hi, lo)                  # where the label starts and ends along this segment, in travel order
        at = lambda t: (t, u[1]) if horizontal else (u[0], t)
        if (enter - a) * sign > 1e-9: pieces.append((u, at(enter)))
        if (b - leave) * sign > 1e-9: pieces.append((at(leave), v))
    return pieces


def process(spec, out):
    """spec: {"nodes": [NODE, ...], "streams": [STREAM, ...]}
    NODE: {"id": "col", "type": "column" | "drum" | "exchanger" | "reactor" | "pump" | "vessel" | "box" | "terminal",
           "label": "Distillation column", "at": [column, row]}   (grid cells, from 0: column grows to the right, row grows downward)
      column: tall tower with trays; drum: horizontal vessel (reflux drum, flash drum); exchanger: condenser, reboiler, heater,
      cooler, heat exchanger; reactor: vessel with a stirrer; pump; vessel: tank, still, receiver; box: any other unit;
      terminal: only a label where a stream enters or leaves (Feed F, Distillate D, Steam), no symbol.
    STREAM: {"from": "F", "to": "col", "label": "Feed", "from_side": "E", "to_side": "W", "style": "dashed"}
      the sides ("N", "E", "S", "W") are optional: by default a stream leaves towards its target. Name a side when two streams
      meet one piece of equipment and must not share a side (the overhead vapour leaves the column's top "N", the reflux
      returns at "N" too, the feed arrives at "W", the bottoms leave at "S"). Streams are routed round other equipment, and
      each label is written on its stream.
    Use it for every flowsheet and process diagram: columns with condenser and reboiler, flash drums, reactors with recycle,
    heat exchangers, pump circuits, a steam still. Keep it to about 10 pieces of equipment, put the main flow on one row
    from left to right, recycles on the row above or below. A terminal's label names the stream there, so give the stream
    itself no label (or a different one); give every other stream a short label (a name or a symbol)."""
    brand()
    nodes, streams = spec.get('nodes') or [], spec.get('streams') or []
    ids = {n.get('id'): n for n in nodes}
    if not nodes or len(ids) != len(nodes): raise ValueError('a process figure needs "nodes", each with its own "id"')
    if len(nodes) > 14: raise ValueError('a process figure holds at most 14 pieces of equipment: split the process in two figures')
    for n in nodes:
        if n.get('type') not in TYPES: raise ValueError(f'unknown equipment type {n.get("type")!r}; use one of {TYPES}')
        if not (isinstance(n.get('at'), (list, tuple)) and len(n['at']) == 2): raise ValueError(f'node {n.get("id")!r} needs "at": [column, row]')
    if len({tuple(n['at']) for n in nodes}) != len(nodes): raise ValueError('two pieces of equipment share a grid cell: give each its own "at"')
    for s in streams:
        if s.get('from') not in ids or s.get('to') not in ids: raise ValueError(f'stream {s.get("from")!r} -> {s.get("to")!r} joins an unknown "id"')

    cols, rows = [n['at'][0] for n in nodes], [n['at'][1] for n in nodes]
    span = max(cols) - min(cols)
    cell_w = min(CELL_W, 10.0 / span) if span else CELL_W              # many columns share the page width: the text keeps its size, the gaps shrink
    centre = lambda n: (n['at'][0] * cell_w, -n['at'][1] * CELL_H)
    xlim = (min(cols) * cell_w - 2.4, max(cols) * cell_w + 2.4)       # room for the names beside the equipment and the streams round the outside; the saved figure is cropped to what is drawn
    ylim = (-max(rows) * CELL_H - 3.2, -min(rows) * CELL_H + 3.2)
    fig, ax = plt.subplots(figsize=((xlim[1] - xlim[0]) * IN_PER_UNIT, (ylim[1] - ylim[0]) * IN_PER_UNIT))
    fig.subplots_adjust(0, 0, 1, 1)                                   # the axes fill the figure, so a size in inches is a size in drawing units
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect('equal'); ax.axis('off')
    fig.canvas.draw()

    def text_size(text):
        t = ax.text(0, 0, text, fontsize=8.5)
        bb = ax.transData.inverted().transform_bbox(t.get_window_extent(fig.canvas.get_renderer())); t.remove()
        return bb.width, bb.height

    size, texts = {}, []
    for n in nodes:                                                   # equipment: its size and symbol
        c, kind, text = centre(n), n['type'], textwrap.fill(str(n.get('label', '')), 14)
        if kind in SIZES: hw, hh = SIZES[kind]
        else:                                                         # sized to its name, which is written inside it
            w, h = text_size(text)
            gap = (0.05, 0.03) if kind == 'terminal' else (0.14, 0.12)
            hw, hh = w / 2 + gap[0], h / 2 + gap[1]
            if kind == 'vessel': hw, hh = max(hw, 0.6), max(hh, 0.5)
            texts.append(ax.text(*c, text, ha='center', va='center', fontsize=8.5, color=INK, zorder=5))
        size[n['id']] = (hw, hh)
        if kind != 'terminal': _draw_equipment(ax, kind, c, hw, hh)

    sides = []                                                       # the side of each end of each stream: given, or towards the other end
    for s in streams:
        (ax_, ay), (bx, by) = centre(ids[s['from']]), centre(ids[s['to']])
        dx, dy = bx - ax_, by - ay
        towards = ('E' if dx > 0 else 'W', 'W' if dx > 0 else 'E') if abs(dx) / cell_w >= abs(dy) / CELL_H else (('N', 'S') if dy > 0 else ('S', 'N'))
        sides.append((str(s.get('from_side') or towards[0]).upper(), str(s.get('to_side') or towards[1]).upper()))
        if not set(sides[-1]) <= set(NORMALS): raise ValueError('"from_side" and "to_side" are "N", "E", "S" or "W"')
    used = {}                                                         # streams sharing one side of a piece of equipment are spread along it
    for k, (a, b) in enumerate(sides):
        used.setdefault((streams[k]['from'], a), []).append((k, 0)); used.setdefault((streams[k]['to'], b), []).append((k, 1))

    boxes = [(c[0] - size[n['id']][0], c[1] - size[n['id']][1], c[0] + size[n['id']][0], c[1] + size[n['id']][1]) for n, c in ((n, centre(n)) for n in nodes)]
    for n in nodes:                                                   # a symbol's name goes under it, or over it, on the side with fewer streams
        if n['type'] not in SIZES or not n.get('label'): continue
        (cx, cy), (hw, hh), text = centre(n), size[n['id']], textwrap.fill(str(n['label']), 14)
        w, h = text_size(text)
        side = min('SN', key=lambda d: len(used.get((n['id'], d), [])))
        k = len(used.get((n['id'], side), []))
        x = cx + (0.3 * (k - 1) / 2 + 0.2 + w / 2 if k else 0)       # clear of the streams on that side
        y = cy - hh - 0.12 if side == 'S' else cy + hh + 0.12
        texts.append(ax.text(x, y, text, ha='center', va='top' if side == 'S' else 'bottom', fontsize=8.5, color=PURPLE, zorder=5))
        boxes.append((x - w / 2, y - h if side == 'S' else y, x + w / 2, y if side == 'S' else y + h))
    bounds = (min(b[0] for b in boxes) - 0.7, min(b[1] for b in boxes) - 0.7, max(b[2] for b in boxes) + 0.7, max(b[3] for b in boxes) + 0.7)

    def port(k, end, align=True):
        node, side = streams[k]['to' if end else 'from'], sides[k][end]
        group = used[(node, side)]
        along = 0.3 * (group.index((k, end)) - (len(group) - 1) / 2)
        (cx, cy), (hw, hh), (nx, ny) = centre(ids[node]), size[node], NORMALS[side]
        if align and ids[node]['type'] == 'terminal' and len(group) == 1 and (sides[k][1 - end] in 'EW') == (side in 'EW'):
            o = port(k, 1 - end, False)[0]                           # a label alone on its side lines up with the stream's other end: no dogleg
            lim = 0.6 * (hh if nx else hw)
            along = max(-lim, min(lim, (o[1] - cy) if nx else (o[0] - cx)))
        return ((cx + nx * hw, cy + along) if nx else (cx + along, cy + ny * hh)), (nx, ny)

    paths = []
    for k in range(len(streams)):
        (p0, n0), (p1, n1) = port(k, 0), port(k, 1)
        paths.append(_route(p0, n0, p1, n1, boxes, paths, bounds))
    labelled, notes = [], []
    for k, (s, path) in enumerate(zip(streams, paths)):
        dash, pieces, text = ('--' if s.get('style') == 'dashed' else '-'), list(zip(path[:-1], path[1:])), textwrap.fill(str(s.get('label') or ''), 10)
        if text:
            w, h = text_size(text)
            box, mode, foot = _label_spot(path, w, h, boxes + labelled, paths[:k] + paths[k + 1:])
            if box:
                labelled.append(box); pieces = _broken(path, box) if mode == 'line' else pieces
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                if mode == 'lifted':                                  # a short line from the label to its stream
                    end = (foot[0], box[1] if cy > foot[1] else box[3]) if abs(cx - foot[0]) < 1e-9 else (box[0] if cx > foot[0] else box[2], foot[1])
                    ax.plot([foot[0], end[0]], [foot[1], end[1]], color='#BDB6CC', lw=0.9, zorder=1)
                texts.append(ax.text(cx, cy, text, ha='center', va='center', fontsize=8.5, color=INK, zorder=5))
            else:                                                     # no free place beside the line either: the label placer finds one
                u, v = max(zip(path[:-1], path[1:]), key=lambda p: abs(p[0][0] - p[1][0]) + abs(p[0][1] - p[1][1]))
                note = ax.annotate(text, ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2), textcoords='offset points', xytext=(0, 4), fontsize=8.5, color=INK, ha='center', va='bottom', zorder=5)
                note.prefer = [(0, 7), (0, -7)] if u[1] == v[1] else [(7, 0), (-7, 0)]
                notes.append(note)
        for u, v in pieces[:-1]: ax.plot([u[0], v[0]], [u[1], v[1]], color=STREAM, lw=1.5, ls=dash, solid_capstyle='butt', zorder=2)
        ax.add_patch(FancyArrowPatch(*pieces[-1], arrowstyle='-|>', mutation_scale=11, color=STREAM, lw=1.5, ls=dash, shrinkA=0, shrinkB=0, zorder=2))
    LBL.place(fig, ax, notes, fixed=texts)
    ISSUES.append(LBL.crowded(fig, ax))
    fig.canvas.draw()                                                 # the canvas was roomy, so nothing is clipped: now fit it to what is drawn
    inv = ax.transData.inverted()
    texts_at = [inv.transform_bbox(t.get_window_extent(fig.canvas.get_renderer())) for t in ax.texts]
    x0, x1 = min([ax.dataLim.x0] + [b.x0 for b in texts_at]) - 0.25, max([ax.dataLim.x1] + [b.x1 for b in texts_at]) + 0.25
    y0, y1 = min([ax.dataLim.y0] + [b.y0 for b in texts_at]) - 0.25, max([ax.dataLim.y1] + [b.y1 for b in texts_at]) + 0.25
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    fig.set_size_inches((x1 - x0) * IN_PER_UNIT, (y1 - y0) * IN_PER_UNIT)
    return save(fig, out)

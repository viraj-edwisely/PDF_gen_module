"""Label placement for matplotlib figures: every label tries positions around its anchor and takes the first one that
touches no other label, the legend or a drawn line, and stays inside the plot. What still collides is counted, so the
drawing check can send the figure back for repair instead of printing overlapping text."""
import numpy as np
import matplotlib.text
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch

# offsets in points around the anchor: right-above first (the usual label position), then the other sides, then further out
AROUND = [(6, 6), (6, -14), (-6, 6), (-6, -14), (0, 12), (0, -18), (12, -4), (-12, -4)]
OFFSETS = [(dx * k, dy * k) for k in (1, 2, 3, 4, 5) for dx, dy in AROUND]
UP_DOWN = [(0, dy) for dy in (0, 12, -12, 24, -24, 36, 48)]
# an arrowed note's text: 8 directions around the point it marks, nearest first, so the arrow stays short
ARROWED = [(round(r * np.cos(a)), round(r * np.sin(a))) for r in (24, 40, 60, 85, 115) for a in np.radians([45, 135, -45, -135, 90, -90, 0, 180])]


def _box(t, r):
    """The text alone (an annotation's arrow is not part of it), slightly padded."""
    if hasattr(t, 'update_positions'): t.update_positions(r)
    return matplotlib.text.Text.get_window_extent(t, r).expanded(1.06, 1.2).padded(3)


def _line_points(ax):
    """Points along every drawn line, in display coordinates, close enough together that a label on a line is noticed."""
    pts = []
    for ln in ax.lines:
        if not isinstance(ln, Line2D) or not ln.get_visible(): continue
        xy = ax.transData.transform(np.column_stack(ln.get_data()).astype(float))
        xy = xy[np.isfinite(xy).all(axis=1)]
        for a, b in zip(xy[:-1], xy[1:]):
            n = int(min(max(np.hypot(*(b - a)) / 4, 1), 200))
            pts.append(a + np.outer(np.linspace(0, 1, n, endpoint=False), b - a))
        if len(xy): pts.append(xy[-1:])
    for p in ax.patches:                          # outlines of shapes and arrows (circles, polygons, forces)
        try:
            if isinstance(p, FancyArrowPatch) and p._posA_posB:      # its path is only right once drawn: use its two ends
                xy = p.get_transform().transform(np.asarray(p._posA_posB, float))
            else: xy = p.get_transform().transform(p.get_path().interpolated(40).vertices)
        except Exception: continue
        xy = xy[np.isfinite(xy).all(axis=1)]
        for a, b in zip(xy[:-1], xy[1:]):
            n = int(min(max(np.hypot(*(b - a)) / 4, 1), 200))
            pts.append(a + np.outer(np.linspace(0, 1, n, endpoint=False), b - a))
    for c in ax.collections:                      # vlines / hlines / stems are LineCollections
        for seg in getattr(c, 'get_segments', lambda: [])():
            seg = ax.transData.transform(np.asarray(seg, float))
            for a, b in zip(seg[:-1], seg[1:]):
                n = int(min(max(np.hypot(*(b - a)) / 4, 1), 200))
                pts.append(a + np.outer(np.linspace(0, 1, n), b - a))
    return np.concatenate(pts) if pts else np.zeros((0, 2))


def _hits(bb, pts):
    if not len(pts): return 0
    return int(((pts[:, 0] > bb.x0) & (pts[:, 0] < bb.x1) & (pts[:, 1] > bb.y0) & (pts[:, 1] < bb.y1)).sum())


def _align(t, d):
    """Text grows away from its anchor: a label to the left of its point is right-aligned, one below it hangs down."""
    t.set_ha('left' if d[0] > 0 else 'right' if d[0] < 0 else 'center')
    t.set_va('bottom' if d[1] > 0 else 'top' if d[1] < 0 else 'center')


def _near(path, pts, r=3):
    """How many points of `path` pass within r pixels of a drawn line."""
    if not len(path) or not len(pts): return 0
    lo, hi = path.min(axis=0) - r, path.max(axis=0) + r
    pts = pts[((pts >= lo) & (pts <= hi)).all(axis=1)]
    if not len(pts): return 0
    return int((np.min(np.hypot(*(path[:, None, :] - pts[None, :, :]).transpose(2, 0, 1)), axis=1) < r).sum())


def _segment(a, b):
    return a + np.outer(np.linspace(0, 1, int(min(max(np.hypot(*(b - a)) / 4, 2), 200))), b - a)


def place(fig, ax, notes, fixed=(), offsets=OFFSETS, lines=True):
    """Move each annotation in `notes` to where it was asked to be, or else to the nearest free spot: its own `prefer`
    offsets, then `offsets` (points) around its point for a plain label; its own `spots` (data) for a label placed in
    data coordinates; for an arrowed note, spots at growing distances around the point the arrow
    marks, so the arrow stays short and never crosses another label. `fixed` are text artists that stay where they
    are but must not be covered. Returns the number of labels that still sit on another label, on a drawn line, or
    outside the plot."""
    fig.canvas.draw()                                   # axes limits and the legend are only final once drawn
    r = fig.canvas.get_renderer()
    placed = [_box(t, r) for t in fixed if t.get_visible() and t.get_text()]
    if ax.get_legend(): placed.append(ax.get_legend().get_window_extent(r))
    pts = _line_points(ax) if lines else np.zeros((0, 2))
    frame = ax.get_window_extent(r) if ax.axison else fig.bbox          # a drawing without axes may use the whole figure
    k = fig.dpi / 72
    bad = 0
    for t in notes:
        if not t.get_text(): continue
        offset, arrowed = t.anncoords == 'offset points', t.arrow_patch is not None
        target = ax.transData.transform(t.xy) if not offset else None
        tries = [(np.array(t.xyann, float), None)]
        if offset: tries += [(np.array(d, float), d) for d in list(getattr(t, 'prefer', [])) + list(offsets)]   # around the point
        elif getattr(t, 'spots', None): tries += [(np.array(p, float), None) for p in t.spots]       # the caller's own spots (inside a shape)
        elif arrowed: tries += [(ax.transData.inverted().transform(target + np.array(d, float) * k), d) for d in ARROWED]
        else:
            base = ax.transData.transform(t.xyann)
            tries += [(ax.transData.inverted().transform(base + np.array(d, float) * k), d) for d in offsets]
        asked = t.get_ha(), t.get_va()
        best = None
        for i, (pos, d) in enumerate(tries):
            t.xyann = tuple(pos)
            if d is None: t.set_ha(asked[0]); t.set_va(asked[1])
            else: _align(t, d)
            bb = _box(t, r)
            outside = not (frame.x0 <= bb.x0 and bb.x1 <= frame.x1 and frame.y0 <= bb.y0 and bb.y1 <= frame.y1)
            hits, crossed, path = _hits(bb, pts), 0, np.zeros((0, 2))
            if offset and not arrowed and np.hypot(*t.xyann) > 24: target = ax.transData.transform(t.xy)      # will get a leader line
            elif offset: target = None
            if target is not None:                      # the arrow or leader from the text to its point: it must not cut through a label
                path = _segment(np.array([(bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2]), target)
                crossed = sum(_hits(p, path) > 1 for p in placed)
                cuts = _near(path[len(path) // 6: -max(len(path) // 6, 3)], pts)        # drawn lines the arrow cuts across
            else: cuts = 0
            score = 1000 * (sum(bb.overlaps(p) for p in placed) + crossed) + 30 * hits + 10 * cuts + 200 * outside + i
            if best is None or score < best[0]: best = (score, t.xyann, t.get_ha(), t.get_va(), bb, path, hits)
            if score == i: break                     # no collision at all: the nearest free spot wins
        score, t.xyann, ha, va, bb, path, hits = best
        t.set_ha(ha); t.set_va(va)
        if score >= 200 or hits > 2: bad += 1          # still on another label or a line, or pushed outside the plot
        placed.append(bb)
        if len(path): pts = np.concatenate([pts, path])  # later labels keep off this arrow too
        if offset and np.hypot(*(np.array(t.xyann, float))) > 24 and not arrowed:
            t.arrowprops = dict(arrowstyle='-', color='#BDB6CC', lw=0.6, shrinkA=0, shrinkB=2)      # far from its point: a thin leader line
            t._arrow_relpos, t.arrow_patch = (0.5, 0.5), FancyArrowPatch((0, 0), (1, 1), **t.arrowprops)
            t.update_positions(r)
    return bad


def collisions(fig, ax):
    """Labels of a finished axes that still overlap each other (tick labels and axis labels excluded)."""
    r = fig.canvas.get_renderer()
    boxes = [_box(t, r) for t in ax.texts if t.get_visible() and t.get_text().strip()]
    return sum(a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1:])

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
        try: xy = p.get_transform().transform(p.get_path().interpolated(40).vertices)
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


def place(fig, ax, notes, fixed=(), offsets=OFFSETS, lines=True):
    """Move each annotation in `notes` to where it was asked to be, or else to the nearest of `offsets` (points around its
    point, or around the asked text position for an arrowed note) that is free. `fixed` are text artists that stay where
    they are but must not be covered. Returns the number of labels that still collide."""
    fig.canvas.draw()                                   # axes limits and the legend are only final once drawn
    r = fig.canvas.get_renderer()
    placed = [_box(t, r) for t in fixed if t.get_visible() and t.get_text()]
    if ax.get_legend(): placed.append(ax.get_legend().get_window_extent(r))
    pts = _line_points(ax) if lines else np.zeros((0, 2))
    frame = ax.get_window_extent(r).expanded(1.02, 1.04)
    k = fig.dpi / 72
    bad = 0
    for t in notes:
        if not t.get_text(): continue
        start = np.array(t.xyann, float)
        to_display = (lambda p: p) if t.anncoords == 'offset points' else (lambda p: ax.transData.transform(p))
        from_display = (lambda p: p) if t.anncoords == 'offset points' else (lambda p: ax.transData.inverted().transform(p))
        base = to_display(start)
        best = None
        if t.anncoords == 'offset points': tries = [start] + [np.array(d, float) for d in offsets]       # around the point
        else: tries = [start] + [from_display(base + np.array(d, float) * k) for d in offsets]          # around the asked text spot
        for i, pos in enumerate(tries):
            t.xyann = tuple(pos)
            bb = _box(t, r)
            outside = not (frame.x0 <= bb.x0 and bb.x1 <= frame.x1 and frame.y0 <= bb.y0 and bb.y1 <= frame.y1)
            score = 1000 * sum(bb.overlaps(p) for p in placed) + 30 * _hits(bb, pts) + 200 * outside + i
            if best is None or score < best[0]: best = (score, t.xyann, bb)
            if score == i: break                     # no collision at all: the nearest free spot wins
        t.xyann = best[1]
        if best[0] >= 1000 or (best[0] % 1000) >= 200: bad += 1          # still on another label, or pushed outside the plot
        placed.append(best[2])
        if np.hypot(*(np.array(t.xyann, float))) > 24 and t.arrow_patch is None and t.anncoords == 'offset points':
            t.arrowprops = dict(arrowstyle='-', color='#BDB6CC', lw=0.6, shrinkA=0, shrinkB=2)      # far from its point: a thin leader line
            t._arrow_relpos, t.arrow_patch = (0.5, 0.5), FancyArrowPatch((0, 0), (1, 1), **t.arrowprops)
            t.update_positions(r)
    return bad


def collisions(fig, ax):
    """Labels of a finished axes that still overlap each other (tick labels and axis labels excluded)."""
    r = fig.canvas.get_renderer()
    boxes = [_box(t, r) for t in ax.texts if t.get_visible() and t.get_text().strip()]
    return sum(a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1:])

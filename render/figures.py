#!/usr/bin/env python3
"""Edwisely-styled figures for topic PDFs - any GATE paper, any subject.

Every figure is described by a small JSON spec inside the content JSON:
    {"type": "figure", "kind": "gantt", "spec": {...}, "title": "...", "caption": "...", "width": 1.0}
The renderers call render(kind, spec), which caches the PNG by content hash.

Kinds: gantt (alias timeline), plot, bars, graph, cells, circuit (here); geometry (fig_geometry.py); block, logic,
mermaid (fig_diagrams.py); beam, mohr, pressure, waveform, spectrum, cycle, control (fig_physics.py: shapes computed from
physics). The exact spec of each kind is the docstring of its function; reference() turns those docstrings and the
GALLERY examples into the text the model reads, so the prompt can never drift from the code.

CLI:  python figures.py <kind> spec.json out.png      (draw one figure)
      python figures.py --gallery out_dir             (draw every GALLERY example)
      python figures.py --reference                   (print the spec reference given to the model)
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from safe_eval import safe_eval as _safe_eval
import tex as TEX
import labels as LBL

from figstyle import (FONTS, PURPLE, LAV, YEL, INK, GREY, PALETTE, DPI, CACHE, ISSUES, col, brand, save,
                      legend, _fmt, _size)


# ---------------------------------------------------------------- gantt / timeline
def gantt(spec, out):
    """spec: {"segments": [[label, start, end], ...]}  (single bar)
         or {"rows": [{"title": "FCFS", "segments": [...]}, ...]}  (one bar per row, shared colours)
    optional: "idle": ["idle"] labels drawn hatched; "colors": {label: colour}; "ticks": "auto"|list;
              "xlabel"; "row_labels": "left" (put row titles left of bar, e.g. pipeline I1..I5);
              "unit" appended to the last tick; "height" per row (inches, default 0.42)."""
    brand()
    rows = spec.get('rows') or [{'title': spec.get('title'), 'segments': spec['segments']}]
    idle = set(x.lower() for x in spec.get('idle', ['idle', '-', '', 'stall', 'bubble']))
    cmap, k = dict(spec.get('colors', {})), 0
    for r in rows:
        for s in r['segments']:
            lab = str(s[0])
            if lab.lower() in idle or lab in cmap: continue
            cmap[lab] = PALETTE[k % len(PALETTE)]; k += 1
    left = spec.get('row_labels') == 'left'
    tmax = max(s[2] for r in rows for s in r['segments']); tmin = min(s[1] for r in rows for s in r['segments'])
    rh = spec.get('height', 0.5)
    gap = 0.0 if left else 0.38
    fig_h = len(rows) * (rh + 0.62) + (len(rows) - 1) * 0.2 + (0.3 * len(rows) if any(r.get('title') for r in rows) and not left else 0)
    fig, ax = plt.subplots(figsize=(spec.get('width', 7.2), min(fig_h, 9)))      # many rows: closer together, not a figure taller than the page
    y = 0; yt = []
    for r in reversed(rows):
        ticks = set()
        for s in r['segments']:
            lab, a, b = str(s[0]), s[1], s[2]
            if lab.lower() in idle:
                ax.barh(y, b - a, left=a, height=rh, color='white', edgecolor='#BDB6CC', hatch='////', lw=0.8)
                ax.text((a + b) / 2, y, lab if lab not in ('-', '') else '', ha='center', va='center', color=GREY, fontsize=8)
            else:
                c = col(cmap.get(lab))
                ax.barh(y, b - a, left=a, height=rh, color=c, edgecolor='white', lw=1.6)
                txt_c = INK if c in ('#D9A400', YEL, LAV, '#FFFFFF') else 'white'
                room = (b - a) / max(tmax - tmin, 1e-9) * spec.get('width', 7.2) * 0.85      # the bar's width in inches
                size = 8 if len(lab) * 0.11 + 0.04 <= room else 6.5 if len(lab) * 0.09 + 0.03 <= room else 0    # a label only where it fits its bar
                if size:
                    ax.text((a + b) / 2, y, lab, ha='center', va='center', color='white' if txt_c == 'white' else INK,
                            fontsize=size, fontweight='medium')
            ticks.update([a, b])
        if spec.get('ticks', 'auto') != 'none':
            tl = spec['ticks'] if isinstance(spec.get('ticks'), list) else sorted(ticks)
            last = [-1e18, -1e18]
            for t in tl:
                lvl = 0 if t - last[0] >= 0.055 * (tmax - tmin) else 1 if t - last[1] >= 0.055 * (tmax - tmin) else 0
                last[lvl] = t
                ax.text(t, y - rh / 2 - 0.12 - 0.2 * lvl, _fmt(t), ha='center', va='top', fontsize=7.5, color=INK)
        if r.get('title'):
            if left: yt.append((y, r['title']))
            else: ax.text(tmin, y + rh / 2 + 0.1, r['title'], ha='left', va='bottom', fontsize=9, color=PURPLE, fontweight='bold')
        y += rh + 0.62 + (0 if left else 0.22)
    ax.set_xlim(tmin - (tmax - tmin) * 0.01, tmax + (tmax - tmin) * 0.02)
    has_t = any(r.get('title') for r in rows) and not left
    top_c = y - rh - 0.62 - (0 if left else 0.22)          # centre of the top bar
    ax.set_ylim(-rh / 2 - 0.62, top_c + rh / 2 + (0.36 if has_t else 0.03))
    ax.axis('off')
    if left:
        for yy, t in yt: ax.text(tmin - (tmax - tmin) * 0.015, yy, t, ha='right', va='center', fontsize=8.5, color=PURPLE, fontweight='bold')
    if spec.get('xlabel'): fig.text(0.5, 0.0, spec['xlabel'], ha='center', fontsize=8, color=GREY)
    return save(fig, out)


# ---------------------------------------------------------------- plot
def plot(spec, out):
    """spec: {"curves": [CURVE...], "xlabel", "ylabel", "title", "xlim", "ylim", "equal": bool, "grid": bool,
              "legend": bool, "points": [{"x","y","label","color"}], "hlines": [y|{y,label,style}],
              "vlines": [...], "annotations": [{"xy":[x,y], "text", "xytext":[x,y]}], "axes_at_zero": bool,
              "size": [w,h] inches, "xticks": [...], "yticks": [...], "logx", "logy", "invert_y": bool (depth downward)}
    CURVE: {"x":[...], "y":[...]}  or  {"expr": "2*x**2 - 3", "range": [a, b]}
           or {"param": ["cx + r*cos(t)", "r*sin(t)"], "range": [0, 6.283]}  (t is the parameter)
           plus optional "label", "color", "style" ('-', '--', ':'), "step": true, "fill": true|colour,
           "stem": true (impulses / line spectra: a vertical line from 0 to each y, with an arrow head),
           "markers": true, "values": true (print y at the given x points), "lw".
    Curves with the same "label" share one colour and one legend entry (a piecewise curve drawn in parts).
    PANELS: {"panels": [{"curves": [...], "ylabel", "title", "ylim", "points", "hlines", "annotations", ...}, ...],
             "xlabel", "xlim", "size"}: axes stacked under one shared x axis, one signal per panel (message, carrier,
             modulated wave with its envelope dashed, demodulated output; a bit train and its ASK/PSK/FSK waveforms)."""
    brand()
    panels = spec.get('panels')
    if panels:
        w, _ = _size(spec)
        h = min(max(float((spec.get('size') or [0, 0])[1] or 0), 1.25 * len(panels) + 0.4), 8.5)
        fig, axes = plt.subplots(len(panels), 1, figsize=(w, h), sharex=True, squeeze=False)
        for i, (ax, p) in enumerate(zip(axes[:, 0], panels)):
            last = i == len(panels) - 1
            _axes(fig, ax, {**{k: spec[k] for k in ('xlim', 'logx') if k in spec}, **p, '_panel': True, 'xlabel': spec.get('xlabel', '') if last else ''})
            if not last: ax.tick_params(labelbottom=False)
        fig.align_ylabels(axes[:, 0])
        return save(fig, out)
    fig, ax = plt.subplots(figsize=_size(spec))
    _axes(fig, ax, spec)
    return save(fig, out)


LINE_STYLES = ['-', '--', '-.', ':']


def _curve_xy(c):
    """x and y of one curve. A formula is sampled finely enough for fast oscillations: when twice as many samples change
    the curve, the sampling is raised (up to about 30,000 points); a carrier still too fast for that is refused, so the
    figure goes back for illustrative frequencies instead of printing an aliased mess."""
    if 'expr' in c:
        a, b = c.get('range', [0, 1])
        f = lambda n: _cut_jumps(_safe_eval(c['expr'], x=np.linspace(a, b, n)) * np.ones(n))
        n = _samples(c)
        while True:
            y, y2 = f(n), f(2 * n)
            span = np.nanmax(np.abs(y2)) if np.isfinite(y2).any() else 1
            fine = np.interp(np.linspace(a, b, 2 * n), np.linspace(a, b, n), y)
            if not np.isfinite(fine - y2).any() or np.nanpercentile(np.abs(fine - y2), 98) <= 0.05 * (span or 1): break    # a jump moves 1-2 points, aliasing most
            if n >= 30_000:
                raise ValueError(f'the curve {c["expr"][:50]!r} oscillates too fast to draw over this range: use illustrative '
                                 'frequencies (for example a carrier 10 to 20 times the message frequency) and say "not to scale"')
            n *= 4
        if np.count_nonzero(np.diff(np.sign(y - np.nanmean(y))) != 0) > 160:      # over about 80 cycles: a solid block of ink
            raise ValueError(f'the curve {c["expr"][:50]!r} shows too many cycles to read: use illustrative frequencies '
                             '(for example a carrier 10 to 20 times the message frequency, a few message cycles) and say "not to scale"')
        return np.linspace(a, b, n), y
    if 'param' in c:
        a, b = c.get('range', [0, 2 * np.pi]); t = np.linspace(a, b, _samples(c))
        return _safe_eval(c['param'][0], t=t) * np.ones_like(t), _safe_eval(c['param'][1], t=t) * np.ones_like(t)
    x, y = np.asarray(c['x'], float), np.asarray(c['y'], float)
    ok = np.isfinite(x) & np.isfinite(y)                 # a NaN or inf point is left out
    return x[ok], y[ok]


def _axes(fig, ax, spec):
    """Draw one set of axes of a plot (the whole figure, or one panel)."""
    curves = spec.get('curves', [])
    names = list(dict.fromkeys(c.get('label') for c in curves if c.get('label') and c.get('lw', 2)))
    spiky, colours, shown, notes = [], {}, set(), []
    for k, c in enumerate(curves):
        x, y = _curve_xy(c)
        if 'expr' in c: spiky.append(y)
        lab = c.get('label') if c.get('lw', 2) else None
        if lab in colours: colr = col(c.get('color'), colours[lab])           # the same series drawn in parts keeps its colour
        else: colr = col(c.get('color'), PALETTE[(names.index(lab) if lab in names else len(names) + k) % len(PALETTE)])
        if lab: colours.setdefault(lab, colr)
        first = bool(lab) and lab not in shown
        shown.add(lab)
        style = c.get('style') or (LINE_STYLES[names.index(lab) % 4] if lab in names and len(names) > 1 else '-')   # readable in greyscale too
        kw = dict(color=colr, lw=c.get('lw', 2), ls=style, label=lab if first else None)
        if c.get('stem'):
            ax.vlines(x, 0, y, color=colr, lw=c.get('lw', 2), label=kw['label'])
            ax.plot(x, y, '^' if c.get('arrow', True) else 'o', color=colr, ms=6)
        elif c.get('step'): ax.step(x, y, where=c.get('where', 'post'), **kw)
        else: ax.plot(x, y, marker='o' if c.get('markers') else None, ms=4, **kw)
        if c.get('fill'):
            fc = colr if c['fill'] is True else col(c['fill'])
            ax.fill_between(x, y, 0, step='post' if c.get('step') else None, color=fc, alpha=0.18 if c['fill'] is True else 0.35, lw=0,
                            label=c.get('label') if c.get('lw', 2) == 0 and c.get('label') not in shown else None)
            if c.get('lw', 2) == 0 and c.get('label'): shown.add(c['label'])
        if c.get('values') and 'x' in c:
            notes += [ax.annotate(_fmt(round(float(yi), 3)), (xi, yi), textcoords='offset points', xytext=(0, 6 if yi >= 0 else -12),
                                  ha='center', fontsize=7.5, color=INK) for xi, yi in zip(x, y)]
    for p in spec.get('points', []):
        ax.plot(p['x'], p['y'], p.get('marker', 'o'), color=col(p.get('color'), PURPLE), ms=5 if p.get('marker', 'o') == 'o' else 8, zorder=5, mfc=p.get('mfc'))
        if p.get('label'):
            notes.append(ax.annotate(p['label'], (p['x'], p['y']), textcoords='offset points', xytext=tuple(p.get('offset', (6, 6))), fontsize=8, color=INK))
    if spec.get('logx'): ax.set_xscale('log')
    if spec.get('logy'): ax.set_yscale('log')
    if spec.get('xlim'): ax.set_xlim(spec['xlim'])
    if spec.get('ylim'): ax.set_ylim(spec['ylim'])
    elif spiky and (lim := _robust_ylim(np.concatenate(spiky))): ax.set_ylim(lim)
    for h in spec.get('hlines', []):
        h = h if isinstance(h, dict) else {'y': h}
        ax.axhline(h['y'], color=col(h.get('color'), GREY), ls=h.get('style', '--'), lw=1)
        if h.get('label'): notes.append(ax.annotate(h['label'], (1, h['y']), xycoords=('axes fraction', 'data'), xytext=(-4, 4),
                                                    textcoords='offset points', ha='right', fontsize=7.5, color=GREY))
    for v in spec.get('vlines', []):
        v = v if isinstance(v, dict) else {'x': v}
        ax.axvline(v['x'], color=col(v.get('color'), GREY), ls=v.get('style', '--'), lw=1)
        if v.get('label'): notes.append(ax.annotate(v['label'], (v['x'], 1), xycoords=('data', 'axes fraction'), xytext=(3, -10),
                                                    textcoords='offset points', fontsize=7.5, color=GREY))
    arrows = [ax.annotate(a['text'], tuple(a['xy']), xytext=tuple(a.get('xytext', a['xy'])), fontsize=8, color=INK,
                          arrowprops=dict(arrowstyle='->', color=GREY, lw=0.8) if a.get('xytext') else None) for a in spec.get('annotations', [])]
    if spec.get('xticks') is not None: ax.set_xticks(spec['xticks'])
    if spec.get('yticks') is not None: ax.set_yticks(spec['yticks'])
    if spec.get('equal'): ax.set_aspect('equal', adjustable='datalim')
    if spec.get('invert_y'): ax.invert_yaxis()
    if spec.get('grid'): ax.grid(True, lw=0.6)
    if spec.get('axes_at_zero'):   # the zero axes as lines through the plot; tick labels stay on the frame, clear of the data
        (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
        if min(y0, y1) < 0 < max(y0, y1): ax.axhline(0, color=INK, lw=0.9, zorder=1.5)
        if x0 < 0 < x1: ax.axvline(0, color=INK, lw=0.9, zorder=1.5)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
        ax.set_xlabel(spec.get('xlabel', ''), loc='right'); ax.set_ylabel(spec.get('ylabel', ''), loc='top', rotation=0, labelpad=-4)
        ax.yaxis.set_label_coords(-0.02, 1.04)
    else:
        ax.set_xlabel(spec.get('xlabel', '')); ax.set_ylabel(spec.get('ylabel', ''))
    lh = legend(ax, len(names), spec.get('_panel')) if spec.get('legend', len(names) >= 2) else 0
    if spec.get('title'): ax.set_title(spec['title'], pad=(16 if spec.get('axes_at_zero') and spec.get('ylabel') else 6) + lh)
    for t in arrows:          # annotation text stays inside the plot box: never in the legend band above it or off the edge
        fx, fy = ax.transAxes.inverted().transform(ax.transData.transform(t.xyann))
        fx, fy = min(max(fx, 0.01), 0.99), min(max(fy, 0.03), 0.93)
        t.xyann = tuple(ax.transData.inverted().transform(ax.transAxes.transform((fx, fy))))
        if fx > 0.7: t.set_ha('right')
    ISSUES.append(LBL.place(fig, ax, notes + arrows))


def _samples(c):
    """Points for an expression curve: enough for fast oscillations, never so many that drawing hangs."""
    try: return min(max(int(c.get('n', 2000)), 2), 5000)
    except (TypeError, ValueError): return 2000


def _cut_jumps(y):
    """An asymptote (1/x, tan x) as a gap, not a vertical line: NaN where y jumps hugely and changes sign."""
    y = np.where(np.isfinite(y), y, np.nan).astype(float)
    dy = np.abs(np.diff(y)); med = np.nanmedian(dy) if np.isfinite(dy).any() else 0
    if med > 0: y[1:][(dy > 50 * med) & (y[1:] * y[:-1] < 0)] = np.nan
    return y


def _robust_ylim(y):
    """y range without the spikes near an asymptote (1st-99th percentile, padded), or None when there are no spikes."""
    y = y[np.isfinite(y)]
    if y.size < 10: return None
    lo, hi = np.percentile(y, [1, 99])
    if y.max() - y.min() <= 5 * (hi - lo) or hi <= lo: return None
    pad = 0.15 * (hi - lo); return lo - pad, hi + pad


# ---------------------------------------------------------------- bars
def bars(spec, out):
    """spec: {"categories": [...], "series": [{"name", "values", "color"}], "stacked": bool, "horizontal": bool,
              "xlabel", "ylabel", "title", "values": bool (label bars), "size": [w,h]}"""
    brand()
    cats = spec['categories']; ser = spec['series']; n = len(ser)
    fig, ax = plt.subplots(figsize=_size(spec))
    x = np.arange(len(cats)); w = 0.8 / (1 if spec.get('stacked') else n); base = np.zeros(len(cats))
    for i, s in enumerate(ser):
        v = np.asarray(s['values'], float); c = col(s.get('color'), PALETTE[i % len(PALETTE)])
        if spec.get('stacked'): pos, bot = x, base
        else: pos, bot = x - 0.4 + w * (i + 0.5), None
        f = ax.barh if spec.get('horizontal') else ax.bar
        r = f(pos, v, w, bot, color=c, label=s.get('name'), edgecolor='white') if not spec.get('horizontal') else \
            ax.barh(pos, v, w, left=bot, color=c, label=s.get('name'), edgecolor='white')
        if spec.get('values', True): ax.bar_label(r, labels=[_fmt(t) for t in v], fontsize=7.5, color=INK,
                                                   label_type='center' if spec.get('stacked') else 'edge', padding=2)
        if spec.get('stacked'): base = base + v
    names = [textwrap.fill(str(c), 14) for c in cats]
    if spec.get('horizontal'): ax.set_yticks(x); ax.set_yticklabels(names)
    else:
        ax.set_xticks(x); ax.set_xticklabels(names, rotation=30 if len(cats) > 8 else 0, ha='right' if len(cats) > 8 else 'center')
    if not spec.get('stacked') and (v := np.concatenate([np.asarray(s_['values'], float) for s_ in ser])).min() < 0:
        ax.axhline(0, color=INK, lw=0.8) if not spec.get('horizontal') else ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlabel(spec.get('xlabel', '')); ax.set_ylabel(spec.get('ylabel', ''))
    lh = legend(ax, n) if n > 1 or spec.get('legend') else 0
    if spec.get('title'): ax.set_title(spec['title'], pad=6 + lh)
    return save(fig, out)


# ---------------------------------------------------------------- graph (graphviz)
def _install_fonts():
    d = os.path.expanduser('~/.fonts')
    if not os.path.exists(os.path.join(d, 'Poppins-Medium.ttf')):
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(FONTS): shutil.copy(os.path.join(FONTS, f), d)
        if shutil.which('fc-cache'): subprocess.run(['fc-cache', '-f', d], capture_output=True)


def node_lines(t):
    """A long node label on several lines: after " = " when it is an equation, otherwise between words (never inside one)."""
    if len(t) <= 18: return [t]
    if ' = ' in t:
        left, right = t.split(' = ', 1)
        return [left + ' ='] + (textwrap.wrap(right, 22, break_long_words=False) or [''])
    return textwrap.wrap(t, 18, break_long_words=False) or ['']


def graph(spec, out):
    """spec: {"nodes": [ID | {"id", "label", "shape" (circle|doublecircle|box|ellipse|point|plaintext|record|diamond),
                             "fill" (purple|lav|accent|gold|teal|white|#hex), "xlabel", "pos": "x,y!" (neato)}],
              "edges": [[a, b] | [a, b, label] | {"from","to","label","highlight": bool,"style": "dashed","dir":"both"}],
              "directed": true, "rankdir": "TB"|"LR", "engine": "dot"|"neato"|"circo", "start": ID (automaton
              entry arrow), "same_rank": [[ids...]], "size": "7,3" (inches), "node_shape": default shape}
    Highlighted edges/nodes use the yellow/purple accent - use them for the answer path, critical path, MST."""
    _install_fonts()
    directed = spec.get('directed', True); arrow = '->' if directed else '--'
    ds = spec.get('node_shape', 'circle')
    labels = [str((n.get('label', n['id']) if isinstance(n, dict) else n)) for n in spec.get('nodes', [])]
    fixed = ds in ('circle', 'doublecircle') and not spec.get('autosize') and all(len(x) <= 4 for x in labels)
    if ds in ('circle', 'doublecircle') and not fixed: ds = 'box'           # circles stay for short state names; long labels sit in compact rounded boxes
    node_style = 'filled,rounded' if ds == 'box' else 'filled'
    q = lambda s: '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'     # every value quoted: nothing breaks the DOT
    L = [('digraph' if directed else 'graph') + ' G {',
         f'graph [rankdir={q(spec.get("rankdir", "TB"))}, bgcolor=transparent, pad=0.15, nodesep={float(spec.get("nodesep", 0.35))}, '
         f'ranksep={float(spec.get("ranksep", 0.45))}, size={q(spec.get("size", "7,6"))}, dpi={DPI}, fontname="Poppins"];',      # 7,6: a big tree may grow downwards
         f'node [shape={q(ds)}, style="{node_style}", fillcolor="{LAV}", color="{PURPLE}", penwidth=1.4, fontname="Poppins Medium", '
         f'fontsize=11, fontcolor="{INK}", width=0.42, height=0.42, fixedsize={"true" if fixed else "false"}, margin="0.14,0.07"];',
         f'edge [color="{GREY}", penwidth=1.2, fontname="Poppins", fontsize=10, fontcolor="{INK}", arrowsize=0.7];']
    for n in spec.get('nodes', []):
        n = n if isinstance(n, dict) else {'id': n}
        a = []
        if 'label' in n:
            lab = str(n['label']) if n.get('shape') == 'record' else '\n'.join(node_lines(str(n['label'])))    # long labels wrap onto several lines
            a.append(f'label={q(lab)}')
        if n.get('shape'):
            if n['shape'] in ('circle', 'doublecircle') and len(str(n.get('label', n['id']))) > 4: n = dict(n, shape='box')
            a.append(f'shape={q(n["shape"])}')
        if n.get('shape') in ('box', 'record', 'plaintext', 'ellipse', 'diamond'): a.append('fixedsize=false'); a.append('style="filled,rounded"' if n['shape'] == 'box' else 'style=filled')
        if n.get('shape') == 'plaintext': a.append('fillcolor=white, color=white')
        f = n.get('fill')
        if f:
            fc = col(f); a.append(f'fillcolor="{fc}"')
            if fc in (PURPLE, '#7B5CB8', '#2E8B87', '#B5487A', '#5A7FBF'): a.append('fontcolor=white')
        if n.get('xlabel'): a.append(f'xlabel={q(n["xlabel"])}')
        if n.get('pos'): a.append(f'pos={q(n["pos"])}')
        L.append(f'{q(n["id"])} [{", ".join(a)}];')
    if spec.get('start') is not None:
        L.append('__start [shape=point, width=0.01, height=0.01, style=invis];')
        L.append(f'__start {arrow} {q(spec["start"])} [color="{PURPLE}"];')
    for e in spec.get('edges', []):
        if isinstance(e, (list, tuple)): e = {'from': e[0], 'to': e[1], 'label': e[2] if len(e) > 2 else None}
        a = []
        if e.get('label') is not None: a.append(f'label={q(" " + _fmt(e["label"]) + " ")}')
        if e.get('highlight'): a += [f'color="{PURPLE}"', 'penwidth=3']
        if e.get('style') in ('dashed', 'dotted', 'solid', 'bold', 'invis'): a.append(f'style={e["style"]}')
        if e.get('dir') in ('forward', 'back', 'both', 'none'): a.append(f'dir={e["dir"]}')
        if e.get('constraint') is False: a.append('constraint=false')
        L.append(f'{q(e["from"])} {arrow} {q(e["to"])} [{", ".join(a)}];')
    for grp in spec.get('same_rank', []): L.append('{rank=same; ' + '; '.join(q(x) for x in grp) + ';}')
    L.append('}')
    with tempfile.NamedTemporaryFile('w', suffix='.dot', delete=False, encoding='utf-8') as f: f.write('\n'.join(L)); dot = f.name
    eng = spec.get('engine', 'dot')
    if eng not in ('dot', 'neato', 'fdp', 'circo', 'twopi'): raise ValueError(f'unknown graphviz engine {eng!r}')
    args = [eng, '-Tpng', dot, '-o', out] + (['-n'] if eng == 'neato' and any(isinstance(n, dict) and n.get('pos') for n in spec.get('nodes', [])) else [])
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode: raise RuntimeError('graphviz: ' + r.stderr[-300:])
    from PIL import Image as PI
    PI.open(out).save(out, dpi=(DPI, DPI))
    return out


# ---------------------------------------------------------------- cells
def cells(spec, out):
    """spec: {"rows": [{"label": "Frames", "cells": ["7", "0", {"text": "1", "fill": "accent", "note": "hit"}, ...]}, ...],
              "index": true (print 0,1,2.. above first row) | [custom headers], "index_start": 0,
              "cell_w": 0.55, "cell_h": 0.42 (inches), "arrows": [{"row": 0, "cell": 2, "text": "top"}]}
    Use for arrays, memory frames over time, page/segment tables, cache sets, registers, stack/queue,
    hash tables, bit fields, Belady/LRU traces (one row per frame, one column per reference)."""
    brand()
    rows = spec['rows']; base, ch = spec.get('cell_w', 0.55), spec.get('cell_h', 0.42)
    ncol = max(len(r['cells']) for r in rows)
    cell = lambda c: c if isinstance(c, dict) else {'text': c}
    text = lambda c: _fmt(cell(c).get('text', '') or '')
    wrapped = lambda t: textwrap.fill(t, max(8, -(-len(t) // 2) + 2)) if len(t) > 16 else t       # long field names on two lines
    width = lambda t: max((len(x) for x in wrapped(t).split('\n')), default=0)
    # each column as wide as its longest text needs at 9 pt, and the whole grid at most about a page wide
    cws = [max([base] + [0.085 * width(text(r['cells'][j])) + 0.16 for r in rows if j < len(r['cells'])]) for j in range(ncol)]
    lab_w = max(1.1, 0.09 * max(len(str(r.get('label', ''))) for r in rows) + 0.2) if any(r.get('label') for r in rows) else 0.05
    if sum(cws) > 6.6 - lab_w: cws = [max(0.3, w * (6.6 - lab_w) / sum(cws)) for w in cws]
    xs = [sum(cws[:j]) for j in range(ncol)]
    fs = max(6.5, min([9.0] + [9 * (cws[j] - 0.1) / (0.085 * width(text(r['cells'][j]))) for r in rows for j in range(len(r['cells'])) if width(text(r['cells'][j]))]))
    ch = max(ch, 0.62) if any('\n' in wrapped(text(c)) for r in rows for c in r['cells']) else ch
    ch = max(0.26, min(ch, 7 / len(rows) - 0.12))          # many rows: lower cells, so the grid stays about a page high
    total = sum(cws)
    fig = plt.figure(figsize=(lab_w + total + 0.2, len(rows) * (ch + 0.12) + 0.45))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(-lab_w, total + 0.1); ax.set_ylim(-0.1, len(rows) * (ch + 0.12) + 0.35); ax.axis('off')
    idx = spec.get('index')
    top = len(rows) * (ch + 0.12)
    if idx:
        hdr = idx if isinstance(idx, list) else [str(spec.get('index_start', 0) + i) for i in range(ncol)]
        for j, h in enumerate(hdr[:ncol]): ax.text(xs[j] + cws[j] / 2, top + 0.06, str(h), ha='center', va='bottom', fontsize=max(fs - 1, 7), color=GREY)
    for i, r in enumerate(rows):
        y = top - (i + 1) * (ch + 0.12) + 0.06
        if r.get('label'): ax.text(-0.08, y + ch / 2, r['label'], ha='right', va='center', fontsize=8.5, color=PURPLE, fontweight='bold')
        for j, c in enumerate(r['cells']):
            c = cell(c)
            if c.get('text') is None and not c.get('fill'): continue
            fc = col(c.get('fill'), LAV) if c.get('fill') else ('white' if c.get('empty') else LAV)
            ax.add_patch(plt.Rectangle((xs[j], y), cws[j], ch, facecolor=fc, edgecolor=PURPLE, lw=1.1))
            tc = 'white' if fc in (PURPLE, '#7B5CB8', '#2E8B87') else INK
            ax.text(xs[j] + cws[j] / 2, y + ch / 2, wrapped(text(c)), ha='center', va='center', fontsize=fs, color=tc, linespacing=1.1)
            if c.get('note'): ax.text(xs[j] + cws[j] / 2, y - 0.02, c['note'], ha='center', va='top', fontsize=6.5, color=GREY)
    for a in spec.get('arrows', []):
        i, j = a['row'], a['cell']; y = top - (i + 1) * (ch + 0.12) + 0.06
        ax.annotate(a['text'], (xs[j] + cws[j] / 2, y + ch), xytext=(xs[j] + cws[j] / 2, y + ch + 0.3), ha='center', fontsize=8,
                    color=PURPLE, arrowprops=dict(arrowstyle='->', color=PURPLE))
    return save(fig, out)


# ---------------------------------------------------------------- beam
# ---------------------------------------------------------------- circuit (schemdraw)
def _anchor(ids, ref):
    """'R1.end' -> the placed element R1's anchor named 'end' (anchor names are checked, not blindly getattr'd)."""
    i, an = ref.split('.')
    if i not in ids: raise ValueError(f'no element with id {i!r} before {ref!r}')
    if an not in ids[i].anchors: raise ValueError(f'unknown anchor {ref!r}; {i} has {sorted(ids[i].anchors)}')
    return getattr(ids[i], an)          # the anchor's position in the drawing (anchors[...] holds it relative to the element)


def circuit(spec, out):
    """spec: {"elements": [{"el": "SourceV"|"Resistor"|"Capacitor"|"Inductor"|"Diode"|"Line"|"Ground"|"Dot"|
                                  "SourceI"|"Switch"|"Opamp"|"Battery"|"Lamp"|"Zener"|"BjtNpn"|"NFet"|...,
                            "dir": "right"|"left"|"up"|"down", "label": "10 Ω", "length": 3,
                            "id": "R1", "at": "R1.end", "to": "R1.start", "tox": "R1.start", "toy": "V1.end",
                            "loc": "top"|"bottom" (label side), "reverse": bool}],
              "unit": 2.5}
    Anchors: start, end, center, and element-specific ones (Opamp: in1, in2, out). Draw nets in order."""
    import schemdraw
    import schemdraw.elements as E
    brand()
    ids = {}
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=spec.get('unit', 2.5), color=PURPLE, fontsize=11, font='DejaVu Sans', lw=1.5)  # Poppins has no Greek (Ω, µ)
        for e in spec['elements']:
            cls = getattr(E, e['el'], None)
            if not (isinstance(cls, type) and issubclass(cls, E.Element)): raise ValueError(f'unknown circuit element {e["el"]!r}')
            el = cls()
            if e.get('reverse'): el = el.reverse()
            if e.get('at'):
                el = el.at(_anchor(ids, e['at']))
            if e.get('dir'):
                if e['dir'] not in ('up', 'down', 'left', 'right'): raise ValueError(f'bad direction {e["dir"]!r}')
                el = getattr(el, e['dir'])()
            if e.get('length'): el = el.length(e['length'])
            for k in ('to', 'tox', 'toy'):
                if e.get(k):
                    el = getattr(el, k)(_anchor(ids, e[k]))
            if e.get('label'): el = el.label(e['label'], loc=e.get('loc', 'top'), color=INK)
            if e.get('color'): el = el.color(col(e['color']))
            d += el
            if e.get('id'): ids[e['id']] = el
        d.save(out, dpi=DPI)
    return out


import fig_diagrams, fig_geometry, fig_physics          # after the shared helpers above: they draw panels with plot()

KINDS = {'gantt': gantt, 'timeline': gantt, 'plot': plot, 'bars': bars, 'graph': graph, 'cells': cells, 'circuit': circuit,
         'geometry': fig_geometry.geometry, 'block': fig_diagrams.block, 'logic': fig_diagrams.logic, 'mermaid': fig_diagrams.mermaid,
         'beam': fig_physics.beam, 'mohr': fig_physics.mohr, 'pressure': fig_physics.pressure, 'waveform': fig_physics.waveform,
         'spectrum': fig_physics.spectrum, 'cycle': fig_physics.cycle, 'control': fig_physics.control,
         'illustration': fig_diagrams.illustration}


GREEK = {'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ', 'kappa': 'κ',
         'lambda': 'λ', 'mu': 'µ', 'nu': 'ν', 'xi': 'ξ', 'pi': 'π', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'phi': 'φ', 'chi': 'χ', 'psi': 'ψ',
         'omega': 'ω', 'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Pi': 'Π', 'Sigma': 'Σ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
         'infty': '∞', 'cdot': '·', 'times': '×', 'leq': '≤', 'le': '≤', 'geq': '≥', 'ge': '≥', 'neq': '≠', 'pm': '±', 'to': '→',
         'rightarrow': '→', 'circ': '°', 'deg': '°', 'approx': '≈'}
SUB = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
MATHTEXT = matplotlib.mathtext.MathTextParser('path')


def text_label(s, plain=False):
    """A figure label as readable text: \\u00bd -> ½, \\omega -> ω, x_0 -> x₀, \\frac{1}{2} -> 1/2. Labels inside $...$ stay maths
    when they draw (a missing closing $ is added), and so does TeX written without $ that text cannot show (\\frac, \\sqrt);
    maths that does not draw becomes text. plain: the figure cannot draw maths at all (graphviz)."""
    s = TEX.plain(s)                                       # m^3, 10^-3, kg/m3 -> m³, 10⁻³, kg/m³
    if '$' in s and not plain:
        m = s + '$' if s.count('$') % 2 else s
        try: MATHTEXT.parse(m); return m
        except Exception: pass
    s = s.replace('$', '')
    if '\\' not in s and '_' not in s: return s
    tex = bool(re.search(r'\\[A-Za-z]{2,}', s))           # braces are TeX grouping only in a TeX label; {1,2} elsewhere is a set
    if tex and not plain and re.search(r'\\(?!(?:%s)\b)[A-Za-z]{2,}' % '|'.join(GREEK), s):
        try: MATHTEXT.parse(f'${s}$'); return f'${s}$'
        except Exception: pass
    s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', lambda m: '/'.join(x if re.fullmatch(r'\w*', x) else f'({x})' for x in m.groups()), s)
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\([A-Za-z]+)', lambda m: GREEK.get(m.group(1), m.group(1)), s)
    s = re.sub(r'_\{?(\d+)\}?', lambda m: m.group(1).translate(SUB), s)
    if not plain:                                          # f_c, A_{max}: a letter subscript as maths, word by word (spaces stay)
        s = re.sub(r'(?<![A-Za-z$\\])([A-Za-zα-ωΑ-Ω])_\{?([A-Za-z]+)\}?', r'$\1_{\2}$', s)
    return s.replace('{', '').replace('}', '') if tex else s


def labels(x, key=None, plain=False):
    """Every text in a spec through text_label, except expressions that are evaluated."""
    if key in ('expr', 'param', 'code', 'wave', 'bits', 'names', 'file', 'concept'): return x          # evaluated or parsed, not printed as written
    if isinstance(x, str): return text_label(x, plain)
    if isinstance(x, list): return [labels(v, key, plain) for v in x]
    if isinstance(x, dict): return {k: labels(v, k, plain) for k, v in x.items()}
    return x


def render(kind, spec, out=None):
    """Render a figure (cached by content hash); returns the PNG path."""
    spec = labels(spec, plain=kind == 'graph')         # graphviz draws text only
    if kind not in KINDS: raise ValueError(f'unknown figure kind {kind!r}; use one of {sorted(KINDS)} or an image block')
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.md5(json.dumps([kind, spec], sort_keys=True).encode()).hexdigest()[:16]
    out = out or os.path.join(CACHE, f'{kind}_{key}.png')
    if not os.path.exists(out):
        ISSUES.clear()
        KINDS[kind](spec, out)
        json.dump({'overlaps': int(sum(ISSUES))}, open(out + '.json', 'w'))       # read back by the drawing check, also for cached figures
    return out




def overlaps(png):
    """How many labels of a drawn figure still collide (0 when unknown)."""
    try: return json.load(open(png + '.json')).get('overlaps', 0)
    except (OSError, ValueError): return 0


GALLERY = {
    'gantt_os_scheduling': ('gantt', {'segments': [['P1', 0, 3], ['idle', 3, 5], ['P2', 5, 7], ['P3', 7, 11]]}),
    'gantt_pipeline': ('gantt', {'row_labels': 'left', 'colors': {'IF': '#4D2A87', 'ID': '#7B5CB8', 'EX': '#D9A400', 'MEM': '#2E8B87', 'WB': '#B5487A'},
                                 'rows': [{'title': 'I1', 'segments': [['IF', 0, 1], ['ID', 1, 2], ['EX', 2, 3], ['MEM', 3, 4], ['WB', 4, 5]]},
                                          {'title': 'I2', 'segments': [['IF', 1, 2], ['ID', 2, 3], ['EX', 3, 4], ['MEM', 4, 5], ['WB', 5, 6]]},
                                          {'title': 'I3', 'segments': [['IF', 2, 3], ['ID', 3, 4], ['stall', 4, 5], ['EX', 5, 6], ['MEM', 6, 7], ['WB', 7, 8]]}]}),
    'plot_sfd_bmd_ce': ('plot', {'size': [6.4, 2.6], 'xlabel': 'x (m)', 'ylabel': 'BM (kN·m)', 'axes_at_zero': True,
                                 'curves': [{'expr': '10*x - 2.5*x**2', 'range': [0, 4], 'fill': True, 'label': 'BMD, UDL 5 kN/m on 4 m SSB'}],
                                 'points': [{'x': 2, 'y': 10, 'label': 'max 10 kN·m at mid-span'}]}),
    'plot_mohr_circle_me': ('plot', {'size': [3.6, 3.2], 'equal': True, 'axes_at_zero': True, 'xlabel': 'σ (MPa)', 'ylabel': 'τ (MPa)',
                                     'curves': [{'param': ['30 + 50*cos(t)', '50*sin(t)'], 'range': [0, 6.2832]}],
                                     'points': [{'x': 80, 'y': 0, 'label': 'σ1 = 80'}, {'x': -20, 'y': 0, 'label': 'σ2 = −20', 'offset': [-62, 6]}, {'x': 60, 'y': 40, 'label': 'A (60, 40)'}]}),
    'plot_bode_ec': ('plot', {'size': [6.0, 2.6], 'logx': True, 'grid': True, 'xlabel': 'ω (rad/s)', 'ylabel': '|G| (dB)',
                              'curves': [{'expr': '-20*log10(sqrt(1 + (x/10)**2))', 'range': [0.1, 1000], 'label': 'G(s) = 1/(1 + s/10)'}],
                              'vlines': [{'x': 10, 'label': 'corner 10 rad/s'}]}),
    'plot_normal_da': ('plot', {'size': [6.0, 2.4], 'xlabel': 'z', 'curves': [{'expr': 'exp(-x**2/2)/sqrt(2*pi)', 'range': [-3.5, 3.5]},
                                {'expr': 'where(abs(x) <= 1.96, exp(-x**2/2)/sqrt(2*pi), 0)', 'range': [-3.5, 3.5], 'fill': 'gold', 'lw': 0, 'label': '95% area'}]}),
    'bars_data_interpretation_ga': ('bars', {'categories': ['2021', '2022', '2023', '2024'], 'ylabel': 'Units (thousands)',
                                             'series': [{'name': 'Product A', 'values': [12, 15, 18, 16]}, {'name': 'Product B', 'values': [9, 11, 10, 14]}]}),
    'graph_dfa_cs': ('graph', {'rankdir': 'LR', 'start': 'q0', 'nodes': ['q0', {'id': 'q1'}, {'id': 'q2', 'shape': 'doublecircle', 'fill': 'gold'}],
                               'edges': [['q0', 'q0', 'b'], ['q0', 'q1', 'a'], ['q1', 'q2', 'b'], ['q1', 'q1', 'a'], ['q2', 'q0', 'a, b']]}),
    'graph_bst_cs': ('graph', {'directed': False, 'nodes': ['50', '30', '70', '20', '40', {'id': '60', 'fill': 'accent'}, '80'],
                               'edges': [['50', '30'], ['50', '70'], ['30', '20'], ['30', '40'], {'from': '70', 'to': '60', 'highlight': True}, ['70', '80']]}),
    'graph_cpm_network_ce': ('graph', {'rankdir': 'LR', 'nodes': [str(i) for i in range(1, 6)],
                                       'edges': [{'from': '1', 'to': '2', 'label': 'A 4', 'highlight': True}, ['1', '3', 'B 3'], {'from': '2', 'to': '4', 'label': 'C 6', 'highlight': True},
                                                 ['3', '4', 'D 5'], {'from': '4', 'to': '5', 'label': 'E 2', 'highlight': True}, ['2', '5', 'F 3']]}),
    'graph_block_diagram_ee': ('graph', {'rankdir': 'LR', 'node_shape': 'box', 'nodes': [{'id': 'r', 'label': 'R(s)', 'shape': 'plaintext'}, {'id': 's', 'label': 'Σ', 'shape': 'circle'},
                                         {'id': 'g', 'label': 'G(s) = K/(s(s+2))', 'shape': 'box'}, {'id': 'c', 'label': 'C(s)', 'shape': 'plaintext'}, {'id': 'h', 'label': 'H(s) = 1', 'shape': 'box'}],
                                         'edges': [['r', 's'], ['s', 'g'], ['g', 'c'], {'from': 'g', 'to': 'h', 'constraint': False}, {'from': 'h', 'to': 's', 'label': '−', 'constraint': False}]}),
    'cells_page_replacement_cs': ('cells', {'index': ['7', '0', '1', '2', '0', '3'], 'rows': [
        {'label': 'Frame 1', 'cells': ['7', '7', '7', '2', '2', '2']}, {'label': 'Frame 2', 'cells': [None, '0', '0', '0', {'text': '0', 'fill': 'accent', 'note': 'hit'}, '3']},
        {'label': 'Frame 3', 'cells': [None, None, '1', '1', '1', '1']}]}),
    'beam_ce_me': ('beam', {'length': 6, 'supports': [{'x': 0, 'type': 'pin'}, {'x': 6, 'type': 'roller'}], 'points': {'A': 0, 'C': 2, 'B': 6},
                            'loads': [{'type': 'point', 'x': 2, 'P': 20}, {'type': 'udl', 'x1': 3, 'x2': 6, 'w': 5}],
                            'dims': [[0, 2, '2 m'], [2, 6, '4 m']]}),
    'circuit_ee_ec': ('circuit', {'elements': [{'el': 'SourceV', 'dir': 'up', 'label': '12 V', 'id': 'V'}, {'el': 'Resistor', 'dir': 'right', 'label': '4 Ω'},
                                               {'el': 'Dot', 'id': 'n'}, {'el': 'Resistor', 'dir': 'down', 'label': '6 Ω', 'loc': 'bottom'},
                                               {'el': 'Line', 'dir': 'left', 'tox': 'V.start'}, {'el': 'Line', 'at': 'n.center', 'dir': 'right', 'length': 2.5},
                                               {'el': 'Capacitor', 'dir': 'down', 'label': '10 µF', 'loc': 'bottom', 'id': 'C'}, {'el': 'Line', 'dir': 'left', 'length': 2.5}]}),
    'geometry_floating_body_me': ('geometry', {'items': [
        {'type': 'surface', 'y': 0, 'x': [-3, 3], 'label': 'waterline'},
        {'type': 'rect', 'at': [-1.5, -1.0], 'w': 3, 'h': 2, 'rotate': 10, 'about': [0, 0], 'fill': 'lav'},
        {'type': 'point', 'at': [0.17, 0.5], 'label': 'G'}, {'type': 'point', 'at': [0.35, -0.5], 'label': "B′"}, {'type': 'point', 'at': [0, 1.4], 'label': 'M'},
        {'type': 'arrow', 'from': [0.17, 0.5], 'to': [0.17, -0.6], 'label': 'W'}, {'type': 'arrow', 'from': [0.35, -0.5], 'to': [0.35, 0.6], 'label': 'F_B'},
        {'type': 'angle', 'center': [0, 0], 'from_deg': 90, 'to_deg': 100, 'r': 0.9, 'label': 'θ = 10°'}]}),
    'geometry_traverse_ce': ('geometry', {'north': True, 'items': [
        {'type': 'point', 'at': [0, 0], 'label': 'A'}, {'type': 'bearing', 'from': [0, 0], 'bearing': 30, 'length': 100, 'label': '100 m, 030°', 'to_label': 'B'},
        {'type': 'bearing', 'from': [50, 86.6], 'bearing': 135, 'length': 80, 'label': '80 m, 135°', 'to_label': 'C'}]}),
    'block_am_modulator_ec': ('block', {'chain': [{'el': 'in', 'label': 'm(t)'}, {'el': 'sum', 'id': 's'}, {'el': 'box', 'label': 'Non-linear\ndevice', 'edge': 'v₁'},
                                                  {'el': 'filter', 'filter': 'bp', 'label': 'BPF at f_c', 'edge': 'v₂'}, {'el': 'out', 'label': 's(t)'}],
                                        'side': [{'el': 'osc', 'label': 'A_c cos 2πf_c t', 'into': 's'}], 'signs': {'s': {'W': '+', 'S': '+'}}}),
    'block_control_loop_ee': ('block', {'chain': [{'el': 'in', 'label': 'R(s)'}, {'el': 'sum', 'id': 's'}, {'el': 'box', 'label': 'G(s)', 'id': 'g'}, {'el': 'out', 'label': 'C(s)'}],
                                        'feedback': [{'from': 'g', 'to': 's', 'box': 'H(s)', 'sign': '−'}], 'signs': {'s': {'W': '+'}}}),
    'logic_kmap_cs': ('logic', {'kmap': {'names': 'ABCD', 'ones': [0, 2, 5, 7, 8, 10, 13, 15], 'groups': [[0, 2, 8, 10], [5, 7, 13, 15]]}}),
    'logic_gates_ee': ('logic', {'expr': '(A and B) or not C', 'out': 'Y'}),
    'mermaid_flow_cs': ('mermaid', {'code': 'flowchart LR\n  A[Process arrives] --> B{Burst shorter than the remaining time?}\n  B -- yes --> C[Pre-empt]\n  B -- no --> D[Keep running]'}),
    'beam_sfd_bmd_ce_me': ('beam', {'length': 8, 'supports': [{'x': 0, 'type': 'pin'}, {'x': 6, 'type': 'roller'}], 'points': {'A': 0, 'B': 6, 'C': 8},
                                    'loads': [{'type': 'udl', 'x1': 0, 'x2': 6, 'w': 10}, {'type': 'point', 'x': 8, 'P': 20}], 'diagrams': ['sfd', 'bmd']}),
    'mohr_me_ce': ('mohr', {'sx': 80, 'sy': -20, 'txy': 30, 'unit': 'MPa'}),
    'pressure_gate_me_ce': ('pressure', {'top_depth': 0.5, 'length': 1.5, 'angle': 90, 'width': 1.0}),
    'waveform_am_ec': ('waveform', {'type': 'AM', 'mu': [0.5, 1.5], 'fm': 1, 'fc': 15, 'cycles': 2}),
    'spectrum_am_ec': ('spectrum', {'type': 'AM', 'fc': 100, 'fm': 5, 'Ac': 10, 'mu': 0.5, 'unit': 'kHz'}),
    'cycle_rankine_me': ('cycle', {'fluid': 'water', 'diagram': 'ts', 'states': [{'name': '1', 'p': 10, 'x': 0}, {'name': '2', 'p': 8000, 's': 0.6493},
                                   {'name': '3', 'p': 8000, 'T': 753.15}, {'name': '4', 'p': 10, 's': 6.7357}],
                                   'processes': [{'from': '1', 'to': '2', 'type': 'isentropic'}, {'from': '2', 'to': '3', 'type': 'isobaric'},
                                                 {'from': '3', 'to': '4', 'type': 'isentropic'}, {'from': '4', 'to': '1', 'type': 'isobaric'}]}),
    'control_step_ee_in': ('control', {'num': [10], 'den': [1, 2, 10], 'plot': 'step', 'time': 6}),
}

def reference():
    """Markdown for the prompt: each kind's spec (its docstring) and one working example per kind from GALLERY."""
    out = []
    for kind, fn in KINDS.items():
        if kind == 'timeline': continue
        ex = next((json.dumps(sp, ensure_ascii=False) for k, sp in GALLERY.values() if k == kind), None)
        head = f'### kind "{kind}"' + (' (alias "timeline")' if kind == 'gantt' else '')
        out.append(head + '\n' + textwrap.dedent('    ' + fn.__doc__.strip()) + (f'\nWorking example spec:\n{ex}' if ex else ''))
    return '\n\n'.join(out)


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--gallery':
        os.makedirs(sys.argv[2], exist_ok=True)
        for name, (k, s) in GALLERY.items():
            try: print('ok  ', render(k, s, os.path.join(sys.argv[2], name + '.png')))
            except Exception as ex: print('FAIL', name, ex)
    elif sys.argv[1:] == ['--reference']:
        sys.stdout.reconfigure(encoding='utf-8'); print(reference())
    elif len(sys.argv) == 4:
        print(render(sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]))
    else:
        print(__doc__)

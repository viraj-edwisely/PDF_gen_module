#!/usr/bin/env python3
"""Edwisely-styled figures for topic PDFs - any GATE paper, any subject.

Every figure is described by a small JSON spec, so a topic content JSON can carry its own figures:
    {"type": "figure", "kind": "gantt", "spec": {...}, "caption": "...", "width": 1.0}
The renderer (build_topic_pdf.py) calls render(kind, spec) and caches the PNG by content hash.

Kinds (spec fields are documented in references/figure_catalogue.md, with subject-wise examples):
    gantt     - time bars on one or more rows: CPU/disk scheduling, pipelining, CPM bar charts, TDM slots
    plot      - x-y curves, functions, parametric curves, points, shading, annotations: SFD/BMD,
                stress-strain, hydrographs, Mohr's circle, Bode, waveforms, distributions, regions
    bars      - grouped or stacked bar chart: data interpretation, histograms, comparisons
    graph     - nodes and edges via graphviz: trees, heaps, BST, automata, DAG/CPM networks, RAG,
                precedence graphs, block diagrams, flowcharts, ER sketches, signal-flow graphs
    cells     - rows of boxed cells: arrays, memory/frames, page tables, cache lines, registers,
                stacks/queues, hash tables, bit fields, K-map style grids
    beam      - structural beam with supports, point loads, UDL/UVL and moments (CE/ME)
    circuit   - electrical circuit via schemdraw (EE/EC/IN); pip-installs schemdraw on first use
    custom    - NOT a JSON kind: write your own matplotlib script, call figures.brand() first,
                save with figures.save(fig, path) and use an `image` block.

CLI:  python3 figures.py <kind> spec.json out.png      (quick look at one figure)
      python3 figures.py --gallery out_dir             (renders one sample of every kind)
"""
import ast, hashlib, json, os, shutil, subprocess, sys, tempfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'assets', 'fonts')
PURPLE, LAV, YEL, INK, GREY, LINE = '#4D2A87', '#F0EBFA', '#FFE100', '#1F1A2E', '#6B6480', '#D9D0EE'
# series palette sampled from the reference PDF: purple, mid-purple, gold, teal, then extras
PALETTE = ['#4D2A87', '#7B5CB8', '#D9A400', '#2E8B87', '#B5487A', '#5A7FBF', '#8C6D1F', '#3F7F4F']
ACCENTS = {'purple': PURPLE, 'lav': LAV, 'yellow': YEL, 'accent': YEL, 'gold': '#D9A400', 'teal': '#2E8B87',
           'mid': '#7B5CB8', 'red': '#C0392B', 'green': '#3F7F4F', 'grey': '#BDB6CC', 'white': '#FFFFFF'}
DPI = 200
CACHE = os.path.join(tempfile.gettempdir(), 'topicpdf_fig')


def col(c, default=PURPLE):
    if c is None: return default
    return ACCENTS.get(c, c)


_branded = False


def brand():
    """Apply Edwisely matplotlib style (Poppins labels, DejaVu for maths-friendly text)."""
    global _branded
    if _branded: return
    for f in os.listdir(FONTS):
        if f.endswith('.ttf'): font_manager.fontManager.addfont(os.path.join(FONTS, f))
    plt.rcParams.update({
        'font.family': ['Poppins', 'DejaVu Sans'], 'font.size': 9, 'mathtext.fontset': 'dejavusans',
        'axes.edgecolor': GREY, 'axes.labelcolor': INK, 'axes.titlecolor': PURPLE, 'axes.titleweight': 'bold',
        'axes.titlesize': 10, 'axes.titlelocation': 'left', 'xtick.color': INK, 'ytick.color': INK,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': False, 'grid.color': LINE,
        'axes.prop_cycle': matplotlib.cycler(color=PALETTE), 'legend.frameon': False, 'savefig.dpi': DPI,
        'axes.unicode_minus': True})
    _branded = True


def save(fig, path):
    fig.savefig(path, dpi=DPI, bbox_inches='tight', pad_inches=0.06, transparent=True)  # blends into lavender boxes
    plt.close(fig)
    return path


def _fmt(v):
    return f'{v:g}' if isinstance(v, (int, float)) else str(v)


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
    fig_h = len(rows) * (rh + 0.42) + (len(rows) - 1) * 0.2 + (0.3 * len(rows) if any(r.get('title') for r in rows) and not left else 0)
    fig, ax = plt.subplots(figsize=(spec.get('width', 7.2), fig_h))
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
                if (b - a) / max(tmax - tmin, 1e-9) > 0.025:
                    ax.text((a + b) / 2, y, lab, ha='center', va='center', color='white' if txt_c == 'white' else INK,
                            fontsize=8, fontweight='medium')
            ticks.update([a, b])
        if spec.get('ticks', 'auto') != 'none':
            tl = spec['ticks'] if isinstance(spec.get('ticks'), list) else sorted(ticks)
            for t in tl:
                ax.text(t, y - rh / 2 - 0.12, _fmt(t), ha='center', va='top', fontsize=7.5, color=INK)
        if r.get('title'):
            if left: yt.append((y, r['title']))
            else: ax.text(tmin, y + rh / 2 + 0.1, r['title'], ha='left', va='bottom', fontsize=9, color=PURPLE, fontweight='bold')
        y += rh + 0.62 + (0 if left else 0.22)
    ax.set_xlim(tmin - (tmax - tmin) * 0.01, tmax + (tmax - tmin) * 0.02)
    has_t = any(r.get('title') for r in rows) and not left
    top_c = y - rh - 0.62 - (0 if left else 0.22)          # centre of the top bar
    ax.set_ylim(-rh / 2 - 0.42, top_c + rh / 2 + (0.36 if has_t else 0.03))
    ax.axis('off')
    if left:
        for yy, t in yt: ax.text(tmin - (tmax - tmin) * 0.015, yy, t, ha='right', va='center', fontsize=8.5, color=PURPLE, fontweight='bold')
    if spec.get('xlabel'): fig.text(0.5, 0.0, spec['xlabel'], ha='center', fontsize=8, color=GREY)
    return save(fig, out)


# ---------------------------------------------------------------- plot
_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Compare, ast.Tuple,
                  ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd,
                  ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


def _safe_eval(expr, **vars_):
    """Evaluate a model-written expression: numbers, x/t, whitelisted numpy functions and arithmetic only
    (no attribute access, subscripts or lambdas), so a hijacked spec cannot run code."""
    env = {k: getattr(np, k) for k in ('sin', 'cos', 'tan', 'exp', 'log', 'log10', 'sqrt', 'abs', 'pi', 'e', 'where',
                                       'maximum', 'minimum', 'heaviside', 'arctan', 'sinh', 'cosh', 'tanh', 'clip', 'sign', 'floor')}
    env.update(vars_)
    tree = ast.parse(str(expr), mode='eval')
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES): raise ValueError(f'expression not allowed: {expr!r}')
        if isinstance(node, ast.Name) and node.id not in env: raise ValueError(f'unknown name {node.id!r} in {expr!r}')
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name): raise ValueError(f'expression not allowed: {expr!r}')
    return eval(compile(tree, '<expr>', 'eval'), {'__builtins__': {}}, env)


def plot(spec, out):
    """spec: {"curves": [CURVE...], "xlabel", "ylabel", "title", "xlim", "ylim", "equal": bool, "grid": bool,
              "legend": bool, "points": [{"x","y","label","color"}], "hlines": [y|{y,label,style}],
              "vlines": [...], "annotations": [{"xy":[x,y], "text", "xytext":[x,y]}], "axes_at_zero": bool,
              "size": [w,h] inches, "xticks": [...], "yticks": [...], "logx", "logy"}
    CURVE: {"x":[...], "y":[...]}  or  {"expr": "2*x**2 - 3", "range": [a, b]}
           or {"param": ["cx + r*cos(t)", "r*sin(t)"], "range": [0, 6.283]}  (t is the parameter)
           plus optional "label", "color", "style" ('-', '--', ':'), "step": true, "fill": true|colour,
           "markers": true, "values": true (print y at the given x points), "lw"."""
    brand()
    fig, ax = plt.subplots(figsize=tuple(spec.get('size', (6.4, 3.0))))
    k = 0
    for c in spec.get('curves', []):
        if 'expr' in c:
            a, b = c.get('range', [0, 1]); x = np.linspace(a, b, c.get('n', 400)); y = _safe_eval(c['expr'], x=x) * np.ones_like(x)
        elif 'param' in c:
            a, b = c.get('range', [0, 2 * np.pi]); t = np.linspace(a, b, c.get('n', 400))
            x = _safe_eval(c['param'][0], t=t) * np.ones_like(t); y = _safe_eval(c['param'][1], t=t) * np.ones_like(t)
        else:
            x, y = np.asarray(c['x'], float), np.asarray(c['y'], float)
        colr = col(c.get('color'), PALETTE[k % len(PALETTE)]); k += 1
        kw = dict(color=colr, lw=c.get('lw', 2), ls=c.get('style', '-'), label=c.get('label') if c.get('lw', 2) else None)
        if c.get('step'): ax.step(x, y, where=c.get('where', 'post'), **kw)
        else: ax.plot(x, y, marker='o' if c.get('markers') else None, ms=4, **kw)
        if c.get('fill'):
            fc = colr if c['fill'] is True else col(c['fill'])
            ax.fill_between(x, y, 0, step='post' if c.get('step') else None, color=fc, alpha=0.18 if c['fill'] is True else 0.35, lw=0,
                            label=c.get('label') if c.get('lw', 2) == 0 else None)
        if c.get('values') and 'x' in c:
            for xi, yi in zip(x, y):
                ax.annotate(_fmt(round(float(yi), 3)), (xi, yi), textcoords='offset points', xytext=(0, 6 if yi >= 0 else -12),
                            ha='center', fontsize=7.5, color=INK)
    for p in spec.get('points', []):
        ax.plot(p['x'], p['y'], 'o', color=col(p.get('color'), PURPLE), ms=5, zorder=5)
        if p.get('label'):
            ax.annotate(p['label'], (p['x'], p['y']), textcoords='offset points', xytext=tuple(p.get('offset', (5, 5))),
                        fontsize=8, color=INK)
    for h in spec.get('hlines', []):
        h = h if isinstance(h, dict) else {'y': h}
        ax.axhline(h['y'], color=col(h.get('color'), GREY), ls=h.get('style', '--'), lw=1)
        if h.get('label'): ax.text(ax.get_xlim()[1], h['y'], ' ' + h['label'], va='center', fontsize=7.5, color=GREY)
    for v in spec.get('vlines', []):
        v = v if isinstance(v, dict) else {'x': v}
        ax.axvline(v['x'], color=col(v.get('color'), GREY), ls=v.get('style', '--'), lw=1)
        if v.get('label'): ax.text(v['x'], ax.get_ylim()[1], v['label'], ha='center', va='bottom', fontsize=7.5, color=GREY)
    for a in spec.get('annotations', []):
        ax.annotate(a['text'], tuple(a['xy']), xytext=tuple(a.get('xytext', a['xy'])), fontsize=8, color=INK,
                    arrowprops=dict(arrowstyle='->', color=GREY, lw=0.8) if a.get('xytext') else None)
    if spec.get('axes_at_zero'):
        ax.spines['left'].set_position('zero'); ax.spines['bottom'].set_position('zero')
    if spec.get('logx'): ax.set_xscale('log')
    if spec.get('logy'): ax.set_yscale('log')
    if spec.get('xlim'): ax.set_xlim(spec['xlim'])
    if spec.get('ylim'): ax.set_ylim(spec['ylim'])
    if spec.get('xticks') is not None: ax.set_xticks(spec['xticks'])
    if spec.get('yticks') is not None: ax.set_yticks(spec['yticks'])
    if spec.get('equal'): ax.set_aspect('equal', adjustable='datalim')
    if spec.get('grid'): ax.grid(True, lw=0.6)
    if spec.get('axes_at_zero'):   # labels at the arrow ends so they never sit on the curve
        ax.set_xlabel(spec.get('xlabel', ''), loc='right'); ax.set_ylabel(spec.get('ylabel', ''), loc='top', rotation=0, labelpad=-4)
        ax.yaxis.set_label_coords(-0.02, 1.04)
    else:
        ax.set_xlabel(spec.get('xlabel', '')); ax.set_ylabel(spec.get('ylabel', ''))
    if spec.get('title'): ax.set_title(spec['title'])
    if spec.get('legend', any(c.get('label') for c in spec.get('curves', []))): ax.legend(fontsize=8)
    return save(fig, out)


# ---------------------------------------------------------------- bars
def bars(spec, out):
    """spec: {"categories": [...], "series": [{"name", "values", "color"}], "stacked": bool, "horizontal": bool,
              "xlabel", "ylabel", "title", "values": bool (label bars), "size": [w,h]}"""
    brand()
    cats = spec['categories']; ser = spec['series']; n = len(ser)
    fig, ax = plt.subplots(figsize=tuple(spec.get('size', (6.4, 3.0))))
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
    (ax.set_yticks if spec.get('horizontal') else ax.set_xticks)(x); (ax.set_yticklabels if spec.get('horizontal') else ax.set_xticklabels)(cats)
    ax.set_xlabel(spec.get('xlabel', '')); ax.set_ylabel(spec.get('ylabel', ''))
    if spec.get('title'): ax.set_title(spec['title'])
    if n > 1 or spec.get('legend'): ax.legend(fontsize=8)
    return save(fig, out)


# ---------------------------------------------------------------- graph (graphviz)
def _install_fonts():
    d = os.path.expanduser('~/.fonts')
    if not os.path.exists(os.path.join(d, 'Poppins-Medium.ttf')):
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(FONTS): shutil.copy(os.path.join(FONTS, f), d)
        if shutil.which('fc-cache'): subprocess.run(['fc-cache', '-f', d], capture_output=True)


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
    L = [('digraph' if directed else 'graph') + ' G {',
         f'graph [rankdir={spec.get("rankdir", "TB")}, bgcolor=transparent, pad=0.15, nodesep={spec.get("nodesep", 0.35)}, '
         f'ranksep={spec.get("ranksep", 0.45)}, size="{spec.get("size", "7,4")}", dpi={DPI}, fontname="Poppins"];',
         f'node [shape={ds}, style="filled", fillcolor="{LAV}", color="{PURPLE}", penwidth=1.4, fontname="Poppins Medium", '
         f'fontsize=11, fontcolor="{INK}", width=0.42, height=0.42, fixedsize={"true" if ds in ("circle", "doublecircle") and not spec.get("autosize") else "false"}];',
         f'edge [color="{GREY}", penwidth=1.2, fontname="Poppins", fontsize=10, fontcolor="{INK}", arrowsize=0.7];']
    q = lambda s: '"' + str(s).replace('"', '\\"') + '"'
    for n in spec.get('nodes', []):
        n = n if isinstance(n, dict) else {'id': n}
        a = []
        if 'label' in n: a.append(f'label={q(n["label"])}')
        if n.get('shape'): a.append(f'shape={n["shape"]}')
        if n.get('shape') in ('box', 'record', 'plaintext', 'ellipse', 'diamond'): a.append('fixedsize=false'); a.append('style="filled,rounded"' if n['shape'] == 'box' else 'style=filled')
        if n.get('shape') == 'plaintext': a.append('fillcolor=white, color=white')
        f = n.get('fill')
        if f:
            fc = col(f); a.append(f'fillcolor="{fc}"')
            if fc in (PURPLE, '#7B5CB8', '#2E8B87', '#B5487A', '#5A7FBF'): a.append('fontcolor=white')
        if n.get('xlabel'): a.append(f'xlabel={q(n["xlabel"])}')
        if n.get('pos'): a.append(f'pos="{n["pos"]}"')
        L.append(f'{q(n["id"])} [{", ".join(a)}];')
    if spec.get('start') is not None:
        L.append('__start [shape=point, width=0.01, height=0.01, style=invis];')
        L.append(f'__start {arrow} {q(spec["start"])} [color="{PURPLE}"];')
    for e in spec.get('edges', []):
        if isinstance(e, (list, tuple)): e = {'from': e[0], 'to': e[1], 'label': e[2] if len(e) > 2 else None}
        a = []
        if e.get('label') is not None: a.append(f'label={q(" " + _fmt(e["label"]) + " ")}')
        if e.get('highlight'): a += [f'color="{PURPLE}"', 'penwidth=3']
        if e.get('style'): a.append(f'style={e["style"]}')
        if e.get('dir'): a.append(f'dir={e["dir"]}')
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
    return out


# ---------------------------------------------------------------- cells
def cells(spec, out):
    """spec: {"rows": [{"label": "Frames", "cells": ["7", "0", {"text": "1", "fill": "accent", "note": "hit"}, ...]}, ...],
              "index": true (print 0,1,2.. above first row) | [custom headers], "index_start": 0,
              "cell_w": 0.55, "cell_h": 0.42 (inches), "arrows": [{"row": 0, "cell": 2, "text": "top"}]}
    Use for arrays, memory frames over time, page/segment tables, cache sets, registers, stack/queue,
    hash tables, bit fields, Belady/LRU traces (one row per frame, one column per reference)."""
    brand()
    rows = spec['rows']; cw, ch = spec.get('cell_w', 0.55), spec.get('cell_h', 0.42)
    ncol = max(len(r['cells']) for r in rows)
    lab_w = 1.1 if any(r.get('label') for r in rows) else 0.05
    fig = plt.figure(figsize=(lab_w + ncol * cw + 0.2, len(rows) * (ch + 0.12) + 0.45))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(-lab_w, ncol * cw + 0.1); ax.set_ylim(-0.1, len(rows) * (ch + 0.12) + 0.35); ax.axis('off')
    idx = spec.get('index')
    top = len(rows) * (ch + 0.12)
    if idx:
        hdr = idx if isinstance(idx, list) else [str(spec.get('index_start', 0) + i) for i in range(ncol)]
        for j, h in enumerate(hdr): ax.text(j * cw + cw / 2, top + 0.06, str(h), ha='center', va='bottom', fontsize=7.5, color=GREY)
    for i, r in enumerate(rows):
        y = top - (i + 1) * (ch + 0.12) + 0.06
        if r.get('label'): ax.text(-0.08, y + ch / 2, r['label'], ha='right', va='center', fontsize=8.5, color=PURPLE, fontweight='bold')
        for j, c in enumerate(r['cells']):
            c = c if isinstance(c, dict) else {'text': c}
            if c.get('text') is None and not c.get('fill'): continue
            fc = col(c.get('fill'), LAV) if c.get('fill') else ('white' if c.get('empty') else LAV)
            ax.add_patch(plt.Rectangle((j * cw, y), cw, ch, facecolor=fc, edgecolor=PURPLE, lw=1.1))
            tc = 'white' if fc in (PURPLE, '#7B5CB8', '#2E8B87') else INK
            ax.text(j * cw + cw / 2, y + ch / 2, _fmt(c.get('text', '')), ha='center', va='center', fontsize=9, color=tc)
            if c.get('note'): ax.text(j * cw + cw / 2, y - 0.02, c['note'], ha='center', va='top', fontsize=6.5, color=GREY)
    for a in spec.get('arrows', []):
        i, j = a['row'], a['cell']; y = top - (i + 1) * (ch + 0.12) + 0.06
        ax.annotate(a['text'], (j * cw + cw / 2, y + ch), xytext=(j * cw + cw / 2, y + ch + 0.3), ha='center', fontsize=8,
                    color=PURPLE, arrowprops=dict(arrowstyle='->', color=PURPLE))
    return save(fig, out)


# ---------------------------------------------------------------- beam
def beam(spec, out):
    """spec: {"length": L, "supports": [{"x": 0, "type": "pin"|"roller"|"fixed"|"hinge"}],
              "loads": [{"type": "point", "x": 2, "label": "10 kN"}, {"type": "udl", "x1": 0, "x2": 4, "label": "5 kN/m"},
                        {"type": "uvl", "x1": 0, "x2": 4, "w1": 0, "w2": 1, "label": "..."},
                        {"type": "moment", "x": 3, "label": "20 kN·m", "ccw": true}],
              "dims": [[x1, x2, "label"], ...] (dimension lines under the beam), "points": {"A": 0, "B": 6}}"""
    brand()
    L = float(spec['length']); s = 6.4 / L
    fig, ax = plt.subplots(figsize=(6.6, 2.3)); ax.set_xlim(-0.08 * L, 1.08 * L); ax.set_ylim(-1.3, 1.6); ax.axis('off')
    ax.add_patch(plt.Rectangle((0, -0.08), L, 0.16, color=PURPLE))
    for sp in spec.get('supports', []):
        x, t = sp['x'], sp.get('type', 'pin')
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
            else:
                ax.plot([x - 1.4 * w, x + 1.4 * w], [-0.42, -0.42], color=INK, lw=1)
    for ld in spec.get('loads', []):
        t = ld['type']
        if t == 'point':
            ax.annotate('', (ld['x'], 0.1), xytext=(ld['x'], 1.05), arrowprops=dict(arrowstyle='-|>', color='#D9A400', lw=2.2))
            ax.text(ld['x'], 1.12, ld.get('label', ''), ha='center', va='bottom', fontsize=8.5, color=INK)
        elif t in ('udl', 'uvl'):
            x1, x2 = ld['x1'], ld['x2']; w1, w2 = (ld.get('w1', 1), ld.get('w2', 1)) if t == 'uvl' else (1, 1)
            h = lambda x: 0.2 + 0.5 * (w1 + (w2 - w1) * (x - x1) / (x2 - x1)) / max(w1, w2)
            xs = np.linspace(x1, x2, max(4, int((x2 - x1) * s / 0.35)))
            ax.fill_between([x1, x2], [0.1, 0.1], [h(x1), h(x2)], color='#2E8B87', alpha=0.15, lw=0)
            ax.plot([x1, x2], [h(x1), h(x2)], color='#2E8B87', lw=1.4)
            for x in xs: ax.annotate('', (x, 0.1), xytext=(x, h(x)), arrowprops=dict(arrowstyle='-|>', color='#2E8B87', lw=1))
            ax.text((x1 + x2) / 2, max(h(x1), h(x2)) + 0.06, ld.get('label', ''), ha='center', va='bottom', fontsize=8.5, color=INK)
        elif t == 'moment':
            from matplotlib.patches import FancyArrowPatch
            r = 0.05 * L; ccw = ld.get('ccw', True)
            a = FancyArrowPatch((ld['x'] + r, 0.25), (ld['x'] - r, 0.25), connectionstyle=f'arc3,rad={0.9 if ccw else -0.9}',
                                arrowstyle='-|>', mutation_scale=10, color='#B5487A', lw=1.8)
            ax.add_patch(a); ax.text(ld['x'], 0.75, ld.get('label', ''), ha='center', fontsize=8.5, color=INK)
    for name, x in spec.get('points', {}).items():
        ax.text(x, -0.72 if spec.get('dims') else -0.68, name, ha='center', va='top', fontsize=9, color=PURPLE, fontweight='bold')
    for d in spec.get('dims', []):
        x1, x2, lab = d; y = -1.02
        ax.annotate('', (x1, y), xytext=(x2, y), arrowprops=dict(arrowstyle='<->', color=GREY, lw=0.9))
        ax.text((x1 + x2) / 2, y - 0.06, lab, ha='center', va='top', fontsize=8, color=INK)
    return save(fig, out)


# ---------------------------------------------------------------- circuit (schemdraw)
def _anchor(ids, ref):
    """'R1.end' -> the placed element R1's anchor named 'end' (anchor names are checked, not blindly getattr'd)."""
    i, an = ref.split('.')
    if an not in ids[i].anchors: raise ValueError(f'unknown anchor {ref!r}')
    return ids[i].anchors[an]


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


KINDS = {'gantt': gantt, 'timeline': gantt, 'plot': plot, 'bars': bars, 'graph': graph, 'cells': cells,
         'beam': beam, 'circuit': circuit}


def render(kind, spec, out=None):
    """Render a figure (cached by content hash); returns the PNG path."""
    if kind not in KINDS: raise ValueError(f'unknown figure kind {kind!r}; use one of {sorted(KINDS)} or an image block')
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.md5(json.dumps([kind, spec], sort_keys=True).encode()).hexdigest()[:16]
    out = out or os.path.join(CACHE, f'{kind}_{key}.png')
    if not os.path.exists(out): KINDS[kind](spec, out)
    return out


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
                            'loads': [{'type': 'point', 'x': 2, 'label': '20 kN'}, {'type': 'udl', 'x1': 3, 'x2': 6, 'label': '5 kN/m'}],
                            'dims': [[0, 2, '2 m'], [2, 6, '4 m']]}),
    'circuit_ee_ec': ('circuit', {'elements': [{'el': 'SourceV', 'dir': 'up', 'label': '12 V', 'id': 'V'}, {'el': 'Resistor', 'dir': 'right', 'label': '4 Ω'},
                                               {'el': 'Dot', 'id': 'n'}, {'el': 'Resistor', 'dir': 'down', 'label': '6 Ω', 'loc': 'bottom'},
                                               {'el': 'Line', 'dir': 'left', 'tox': 'V.start'}, {'el': 'Line', 'at': 'n.center', 'dir': 'right', 'length': 2.5},
                                               {'el': 'Capacitor', 'dir': 'down', 'label': '10 µF', 'loc': 'bottom', 'id': 'C'}, {'el': 'Line', 'dir': 'left', 'length': 2.5}]}),
}

if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--gallery':
        os.makedirs(sys.argv[2], exist_ok=True)
        for name, (k, s) in GALLERY.items():
            try: print('ok  ', render(k, s, os.path.join(sys.argv[2], name + '.png')))
            except Exception as ex: print('FAIL', name, ex)
    elif len(sys.argv) == 4:
        print(render(sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]))
    else:
        print(__doc__)

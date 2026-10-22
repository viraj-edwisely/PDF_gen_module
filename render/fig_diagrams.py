"""Diagram figure kinds: signal block diagrams (schemdraw.dsp), logic circuits, Karnaugh maps and timing diagrams
(schemdraw.logic), and Mermaid diagrams (flowcharts, state, sequence, ER, class, mind maps, timelines).
Each kind's exact spec is its docstring: figures.reference() gives it to the model."""
import io, re
from figstyle import PURPLE, INK, GREY, DPI, ISSUES, brand
import labels as LBL

BLOCKS = {'box': 'Box', 'mixer': 'Mixer', 'sum': 'Sum', 'osc': 'Oscillator', 'oscillator': 'Oscillator', 'filter': 'Filter',
          'amp': 'Amp', 'antenna': 'Antenna', 'adc': 'Adc', 'dac': 'Dac', 'speaker': 'Speaker', 'square': 'Square', 'demod': 'Demod'}


def _width(text, per_char=0.16, pad=0.5):
    """Width in drawing units that the longest line of a label needs."""
    return per_char * max((len(x) for x in str(text).split('\n')), default=4) + pad


def _element(item, dsp):
    """One block of the chain, sized to its label."""
    kind = str(item.get('el', 'box')).lower()
    if kind not in BLOCKS: raise ValueError(f'unknown block {kind!r}; use one of {sorted(BLOCKS)} (and "in"/"out" for the ends)')
    lab = str(item.get('label', ''))
    if kind == 'box':
        return dsp.Box(w=max(1.6, _width(lab)), h=1.0 if '\n' not in lab else 1.4).label(lab, fontsize=10), False
    if kind == 'filter':
        resp = {'lp': 'lp', 'lpf': 'lp', 'low': 'lp', 'bp': 'bp', 'bpf': 'bp', 'band': 'bp', 'hp': 'hp', 'hpf': 'hp', 'high': 'hp'}.get(str(item.get('filter', 'lp')).lower(), 'lp')
        return getattr(dsp, 'Filter')(response=resp), True
    return getattr(dsp, BLOCKS[kind])(), kind not in ('amp', 'adc', 'dac')


def block(spec, out):
    """spec: {"chain": [ITEM, ...] (left to right, joined by arrows),
              "side": [{"el": "osc"|"box"|..., "label", "into": ID, "from": "bottom"|"top", "edge": "arrow label"}],
              "feedback": [{"from": ID, "to": ID, "box": "H(s)", "sign": "−"}],
              "signs": {ID: {"W": "+", "S": "−"}}}
    ITEM: {"el": "in" | "out" | "box" | "mixer" | "sum" | "osc" | "filter" | "amp" | "antenna" | "adc" | "dac" | "speaker" | "demod",
           "label": text (inside a box; beside other symbols), "id": name for "side"/"feedback", "edge": label on the arrow
           INTO this item, "filter": "lp"|"bp"|"hp"}.
    "in" and "out" are the signal names at the two ends (m(t), s(t)). Use for modulators, demodulators, receivers,
    transmitters and control loops: a mixer (×) for multiplication, a sum (Σ circle) for addition, an oscillator for a
    carrier or local oscillator fed in from below."""
    import schemdraw
    import schemdraw.dsp as dsp
    import schemdraw.elements as elm
    brand()
    ids = {}
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=10, font='DejaVu Sans', color=PURPLE, lw=1.3, unit=1.4)
        for k, item in enumerate(spec['chain']):
            kind = str(item.get('el', 'box')).lower()
            if kind == 'in':
                d += dsp.Line().right(0.6).label(str(item.get('label', '')), 'left', color=INK)
                continue
            arrow = dsp.Arrow().right(max(1.3, _width(item['edge'], 0.145, 0.3)) if item.get('edge') else 0.9)    # long enough for its label
            if item.get('edge'): arrow = arrow.label(str(item['edge']), 'top', fontsize=9, color=INK)
            if kind == 'out':
                d += arrow.length(1.2).label(str(item.get('label', '')), 'right', color=INK)
                continue
            if k: d += arrow
            el, beside = _element(item, dsp)
            el = el.anchor('W')
            if beside and item.get('label'): el = el.label(str(item['label']), 'top' if item.get('label_at', 'top') == 'top' else 'bottom', fontsize=9, color=INK, ofst=0.15)
            d += el
            d.here = el.E                       # a box does not move the pen past itself: the next arrow starts at its right side
            if item.get('id'): ids[item['id']] = el
        for s in spec.get('side', []):
            tgt = ids.get(s.get('into'))
            if tgt is None: raise ValueError(f'"side" element goes into {s.get("into")!r}, which is not an id in the chain')
            below = s.get('from', 'bottom') != 'top'
            port = tgt.S if below else tgt.N
            el, beside = _element(s, dsp)
            el = el.at((port[0], port[1] + (-1.6 if below else 1.6))).anchor('N' if below else 'S')
            if s.get('label'): el = el.label(str(s['label']), 'right' if beside else 'center', fontsize=9, color=INK, ofst=0.2)
            d += el
            a = dsp.Arrow().at(el.N if below else el.S).to(port)
            if s.get('edge'): a = a.label(str(s['edge']), 'left', fontsize=9, color=INK)
            d += a
        for f in spec.get('feedback', []):
            src, dst = ids.get(f.get('from')), ids.get(f.get('to'))
            if src is None or dst is None: raise ValueError('"feedback" needs "from" and "to" ids that are in the chain')
            y = min(src.S[1], dst.S[1]) - 1.6
            start = (src.E[0] + 0.5, src.E[1])
            d += dsp.Dot().at(start)
            d += dsp.Line().at(start).toy(y)
            if f.get('box'):
                mid, w = (start[0] + dst.S[0]) / 2, max(1.8, _width(f['box']))
                d += dsp.Arrow().at((start[0], y)).tox(mid + w / 2)
                d += (b := dsp.Box(w=w, h=0.9 if '\n' not in str(f['box']) else 1.3).anchor('E').at((mid + w / 2, y)).label(str(f['box']), fontsize=10))
                d += dsp.Line().at(b.W).tox(dst.S[0])
            else: d += dsp.Line().at((start[0], y)).tox(dst.S[0])
            d += dsp.Arrow().at((dst.S[0], y)).to(dst.S)
            if f.get('sign'): d += elm.Label().at((dst.S[0] - 0.25, dst.S[1] - 0.35)).label(str(f['sign']), fontsize=12, color=INK)
        for i, signs in (spec.get('signs') or {}).items():
            el = ids.get(i)
            if el is None: continue
            for side, sign in signs.items():
                p = getattr(el, side, None)
                dx, dy = {'W': (-0.3, 0.3), 'E': (0.3, 0.3), 'N': (-0.3, 0.35), 'S': (-0.3, -0.35)}.get(side, (-0.3, 0.3))   # beside the input, outside the circle
                if p is not None: d += elm.Label().at((p[0] + dx, p[1] + dy)).label(str(sign), fontsize=12, color=INK)
    fig = d.draw(show=False)                                  # schemdraw places its own labels: count the ones that collide, like the other kinds
    ISSUES.append(LBL.crowded(fig.getfig(), fig.ax))
    fig.save(out, dpi=DPI)
    return out


def logic(spec, out):
    """spec: one of
       {"expr": "(A and B) or not C", "out": "Y"}   a gate circuit drawn from a Boolean expression (and, or, not, xor,
                                                     nand, nor; brackets for grouping);
       {"kmap": {"names": "ABCD", "ones": [0, 2, 5, 7], "dont_care": [15], "groups": [[0, 2], [5, 7]]}}   a Karnaugh map
           (2 to 4 variables; minterm numbers; each group a list of minterms, drawn as a coloured loop);
       {"timing": {"signal": [{"name": "CLK", "wave": "p......"}, {"name": "Q", "wave": "0.1..0."}]}}   a timing diagram
           (WaveDrom wave strings: p clock, 0/1 levels, . hold, x unknown, = data)."""
    import schemdraw
    import schemdraw.logic as lg
    brand()
    if spec.get('expr'):
        from schemdraw.parsing import logicparse
        expr = re.sub(r'[·.]', ' and ', re.sub(r'\+', ' or ', str(spec['expr'])))
        d = logicparse(expr, outlabel=spec.get('out', 'Y'))
        for e in d.elements: e.color(PURPLE)
        d.save(out, dpi=DPI)
        return out
    with schemdraw.Drawing(show=False) as d:
        d.config(color=PURPLE, fontsize=11, font='DejaVu Sans')
        if spec.get('kmap'):
            k = spec['kmap']; names = str(k.get('names', 'ABCD')); n = len(names)
            if not 2 <= n <= 4: raise ValueError('a Karnaugh map has 2 to 4 variables')
            ones, dc = {int(m) for m in k.get('ones', [])}, {int(m) for m in k.get('dont_care', [])}
            table = [(format(m, f'0{n}b'), '1' if m in ones else 'X' if m in dc else '0') for m in range(2 ** n)]
            colours = ['#D9A400', '#2E8B87', '#B5487A', '#5A7FBF', '#7B5CB8', '#3F7F4F']
            groups = {}
            for i, g in enumerate(k.get('groups', [])):
                bits = [format(int(m), f'0{n}b') for m in g]
                pattern = ''.join(c[0] if len(set(c)) == 1 else '.' for c in zip(*bits))      # the variables that stay fixed in the group
                groups[pattern] = {'color': colours[i % len(colours)], 'lw': 2}
            d += lg.Kmap(names=names, truthtable=table, groups=groups)
        elif spec.get('timing'):
            d += lg.TimingDiagram(spec['timing'], ygap=0.5, grid=True)
        else: raise ValueError('a logic figure needs "expr", "kmap" or "timing"')
        d.save(out, dpi=DPI)
    return out


FONT = 'Arial'
THEME = ('%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#F0EBFA", "primaryBorderColor": "#4D2A87", '
         '"primaryTextColor": "#1F1A2E", "lineColor": "#6B6480", "secondaryColor": "#FFF6CC", "tertiaryColor": "#FFFFFF", '
         '"fontFamily": "Arial", "fontSize": "15px"}}}%%\n')       # a face the painter has a metric-compatible copy of, so the layout's text sizes are close


def mermaid(spec, out):
    """spec: {"code": "flowchart LR\\n  A[Message] --> B[Modulator] --> C[Channel]", "width": 1600 (pixels, optional)}
    Mermaid text for process and concept diagrams: flowchart (TD or LR) for algorithms, procedures, decision rules and
    concept maps; stateDiagram-v2; sequenceDiagram (protocol exchanges such as the TCP handshake); erDiagram; classDiagram;
    mindmap; timeline. Labels are plain text (no LaTeX): write ω, ², → as characters. Never for plots, circuits, beams or
    anything drawn to scale."""
    from PIL import Image as PI
    code = str(spec['code']).strip()
    if not code.startswith('%%{init'): code = THEME + code
    width = int(min(max(float(spec.get('width', 1600)), 600), 2200))
    try:
        import mmdr
        png = _paint(_fit_labels(mmdr.render(code).svg()), width)
    except ImportError: png = _kroki(code)            # no offline renderer installed: the public one (only the diagram text is sent)
    except Exception as e:
        raise ValueError(f'the Mermaid code does not parse: {str(e).splitlines()[0][:160] if str(e) else type(e).__name__}')
    im = PI.open(io.BytesIO(png))
    im.save(out, dpi=(DPI, DPI))
    return out


def _fit_labels(svg):
    """The layout sizes each edge label's backing box with its own estimate of the text width, and the painter's font is wider, so
    the text sticks out of the box (and off the canvas). Measure each label with the painter's own font and shrink it to its box."""
    import html
    import novasvg.fonts as F
    face = F.get_font_face_for_family_stack(FONT)
    def fit(m):
        box, text = float(m['w']), html.unescape(m['text'])
        wide = F.Font(face, float(m['size'])).measure_text(text)
        size = float(m['size']) * min(1, (box - 6) / wide) if wide else float(m['size'])
        return m['head'] + f'font-size:{round(max(size, 9), 1):g}px' + m['tail']
    return re.sub(r'(?P<head><rect x="[^"]*" y="[^"]*" width="(?P<w>[\d.]+)"[^>]*/><text[^>]*style="[^"]*?)font-size:(?P<size>[\d.]+)px(?P<tail>[^"]*"[^>]*>(?P<text>[^<]*)</text>)', fit, svg)


def _paint(svg, width):
    import novasvg
    doc = novasvg.Document.load_from_data(svg)
    if doc is None: raise ValueError('the Mermaid diagram could not be drawn')
    return doc.render_to_bitmap(width, -1, novasvg.Color(0, 0, 0, 0)).to_png()


def _kroki(code):
    import requests
    r = requests.post('https://kroki.io/mermaid/png', data=code.encode('utf-8'), headers={'Content-Type': 'text/plain'}, timeout=30)
    if r.status_code != 200: raise ValueError(f'the Mermaid code could not be drawn: {r.text[:160]}')
    return r.content


def illustration(spec, out):
    """spec: {"concept": "four_stroke_si_engine" (a short key: one concept, one picture, reused by every PDF),
              "title": "Four-stroke SI engine", "description": "what the picture shows, for the illustrator: the view, the
              state and the parts (e.g. a cut-away of one cylinder during the intake stroke, inlet valve open, piston moving down)",
              "parts": ["Piston", "Inlet valve", "Exhaust valve", "Spark plug"] (the image model numbers them 1, 2, 3 ... on the picture, in this order)}
    A picture for what a student must recognise rather than read values from: real apparatus and cut-aways (an IC
    engine, a centrifugal pump, a Pelton wheel, a lathe, a casting mould, a test rig, tray types, a heat-exchanger cut-away).
    Never for flowsheets, graphs, diagrams with numbers, circuits or anything drawn to scale. The app takes it from its library; a new
    concept is drawn once (only when the run allows new pictures), with no check or redraw. For a question, every value the
    student needs is in the question text: the picture only shows the arrangement."""
    import matplotlib.pyplot as plt
    from PIL import Image as PI
    from figstyle import save
    if not spec.get('file'): raise ValueError(f'the illustration "{spec.get("concept")}" is not approved yet')
    brand()
    im = PI.open(spec['file'])
    parts = [str(p) for p in spec.get('parts', [])]
    rows = -(-len(parts) // 2)
    w = 6.2; h = w * im.height / im.width
    fig = plt.figure(figsize=(w, h + 0.24 * rows + 0.3))
    ax = fig.add_axes([0, (0.24 * rows + 0.3) / (h + 0.24 * rows + 0.3), 1, h / (h + 0.24 * rows + 0.3)]); ax.imshow(im); ax.axis('off')
    for k, p in enumerate(parts):
        col_, row = k // rows if rows else 0, k % rows if rows else 0
        fig.text(0.04 + 0.5 * col_, (0.24 * (rows - row) + 0.05) / (h + 0.24 * rows + 0.3), f'{k + 1}  {p}', fontsize=9, color=INK)
    fig.text(0.99, 0.01, 'Illustration (not to scale)', ha='right', fontsize=7, color=GREY)
    return save(fig, out)

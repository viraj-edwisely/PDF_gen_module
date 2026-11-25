"""The circuit figure kind: a netlist on a grid. The writer gives every node a grid point and every part as SPICE writes it
(name, type, nodes, value); the code draws the parts with schemdraw, adds the junction dots and ground symbols, and refuses
a circuit a textbook would never print (a part left open, a part shorted by a wire, lines crossing or running over a node),
saying exactly what to change. Its exact spec is the docstring of circuit(): figures.reference() gives it to the model."""
import schemdraw
import schemdraw.elements as E
from figstyle import PURPLE, INK, DPI, ISSUES, brand
import labels as LBL

G = 1.5                       # drawing units per grid step: a symbol is about 1 unit long
# two-terminal parts: the schemdraw element, half its width across the line (for labels), and whether it is drawn from the second node
TWO = {'R': (E.Resistor, 0.3, False), 'C': (E.Capacitor, 0.3, False), 'L': (E.Inductor, 0.3, False), 'Fuse': (E.Fuse, 0.3, False),
       'Lamp': (E.Lamp, 0.55, False), 'SW': (E.Switch, 0.5, False), 'AM': (E.MeterA, 0.55, False), 'VM': (E.MeterV, 0.55, False),
       'V': (E.SourceV, 0.55, True), 'Vac': (E.SourceSin, 0.55, True), 'Bat': (E.Battery, 0.45, False), 'Vdep': (E.SourceControlledV, 0.55, True),
       'I': (E.SourceI, 0.55, False), 'Idep': (E.SourceControlledI, 0.55, False),
       'Z': (E.ResistorIEC, 0.3, False), 'D': (E.Diode, 0.3, False), 'Zener': (E.Zener, 0.3, False), 'LED': (E.LED, 0.35, False), 'W': (E.Line, 0, False)}
# parts with 3 or 4 pins: their pins relative to "at" (grid steps, in the order the netlist lists them) and their body (x0, y0, x1, y1)
PINS = {'opamp': ([(-1, 0.5), (-1, -0.5), (1, 0)], (-0.87, -1, 0.87, 1)),
        'npn': ([(-1, 0), (0, 1), (0, -1)], (-0.5, -0.47, 0.25, 0.47)), 'pnp': ([(-1, 0), (0, -1), (0, 1)], (-0.5, -0.47, 0.25, 0.47)),
        'nmos': ([(-1, 0), (0, 1), (0, -1)], (-0.92, -0.5, 0.05, 0.5)), 'pmos': ([(-1, 0), (0, -1), (0, 1)], (-0.92, -0.5, 0.05, 0.5)),
        'xfmr': ([(-1, 1), (-1, -1), (1, 1), (1, -1)], (-0.63, -1, 0.63, 1))}
PIN_NAMES = {'opamp': 'in−, in+, out', 'npn': 'base, collector, emitter', 'pnp': 'base, collector, emitter',
             'nmos': 'gate, drain, source', 'pmos': 'gate, drain, source', 'xfmr': 'p1, p2, s1, s2'}


def _parse(p):
    """One netlist entry as (name, type, nodes, label, options); a list [name, type, node..., label?, {options}?] or a dict."""
    if isinstance(p, dict):
        p = [p.get('name', ''), p.get('type', ''), *p.get('nodes', []), p.get('label', p.get('name', '')), {k: v for k, v in p.items() if k not in ('name', 'type', 'nodes', 'label')}]
    if not isinstance(p, list) or len(p) < 2: raise ValueError(f'a part must be [name, type, node, node, label]: got {p!r}')
    name, typ, rest = str(p[0]), str(p[1]), list(p[2:])
    if typ not in TWO and typ not in PINS: raise ValueError(f'part {name!r} has unknown type {typ!r}; use one of {sorted(TWO) + sorted(PINS)}')
    n = 2 if typ in TWO else len(PINS[typ][0])
    opts = rest.pop() if rest and isinstance(rest[-1], dict) else {}
    if len(rest) < n: raise ValueError(f'part {name!r} ({typ}) needs {n} nodes' + (f' ({PIN_NAMES[typ]})' if typ in PINS else ''))
    label = str(rest[n]) if len(rest) > n else ('' if typ == 'W' else name)
    return name, typ, [str(x) for x in rest[:n]], label, opts


def _layout(spec, canon):
    """Node positions (grid steps), the parts parsed, the straight lines [(owner, p, q)] and the bodies of the multi-pin parts."""
    if 'elements' in spec and 'parts' not in spec: raise ValueError('circuit takes "nodes" and "parts" (a netlist on a grid), not "elements"')
    nodes = {canon(k): tuple(round(float(c), 3) for c in v) for k, v in (spec.get('nodes') or {}).items()}
    parts, lines, bodies = [(n, t, [canon(x) for x in ns], lb, o) for n, t, ns, lb, o in map(_parse, spec.get('parts') or [])], [], []
    for name, typ, ns, label, opts in sorted(parts, key=lambda p: p[1] not in PINS):      # parts with pins first: they place their pin nodes
        if typ in PINS:
            if not isinstance(opts.get('at'), list): raise ValueError(f'{name} ({typ}) needs "at": [x, y]; the app places its pins ({PIN_NAMES[typ]})')
            x, y = (float(c) for c in opts['at'])
            pins, (bx0, by0, bx1, by1) = PINS[typ]
            if opts.get('flip') and typ == 'opamp': pins = [pins[1], pins[0], pins[2]]
            for node, (dx, dy), pin in zip(ns, pins, PIN_NAMES[typ].split(', ')):
                at = (round(x + dx, 3), round(y + dy, 3))
                if nodes.setdefault(node, at) != at:
                    raise ValueError(f'{name} puts its {pin} pin at {list(at)}, but node {node!r} is at {list(nodes[node])}: leave pin nodes out of "nodes" (the app places them) or move the part')
            bodies.append((name, (x + bx0, y + by0, x + bx1, y + by1), [nodes[n] for n in ns]))
        elif any(x not in nodes for x in ns):
            raise ValueError(f'{name or typ} joins node {next(x for x in ns if x not in nodes)!r}, which is not in "nodes"')
    split, seen = [], set()
    for part in parts:              # a wire running over nodes is joined to them (as the picture shows): split it there; a repeated wire is drawn once
        name, typ, ns, label, opts = part
        p, q = (nodes[ns[0]], nodes[ns[1]]) if typ == 'W' else (None, None)
        if typ != 'W' or (p[0] != q[0] and p[1] != q[1]): split.append(part); continue
        chain = [ns[0], *sorted((n for n, pt in nodes.items() if _on(pt, p, q)), key=lambda n: abs(nodes[n][0] - p[0]) + abs(nodes[n][1] - p[1])), ns[1]]
        for u, v in zip(chain, chain[1:]):
            if frozenset((u, v)) not in seen: seen.add(frozenset((u, v))); split.append(('', 'W', [u, v], '', {}))
    for name, typ, ns, _, _ in split:
        if typ in TWO: lines.append((name or f'the wire {ns[0]}-{ns[1]}', nodes[ns[0]], nodes[ns[1]], ns))
    return nodes, split, lines, bodies


def _on(pt, p, q):
    """pt lies on the segment p-q, strictly between its ends."""
    return pt not in (p, q) and min(p[0], q[0]) <= pt[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= pt[1] <= max(p[1], q[1]) and \
        (p[0] == q[0] == pt[0] or p[1] == q[1] == pt[1])


def _meets(a, b):
    """How two axis-parallel segments meet badly: 'overlap' (along one line), 'cross' (through each other) or ''."""
    (p, q), (r, s) = a, b
    ha, hb = p[1] == q[1], r[1] == s[1]
    if ha == hb:
        k, j = (1, 0) if ha else (0, 1)                      # k: the shared coordinate, j: along the line
        if p[k] != r[k]: return ''
        lo, hi = max(min(p[j], q[j]), min(r[j], s[j])), min(max(p[j], q[j]), max(r[j], s[j]))
        return 'overlap' if hi > lo else ''
    h, v = (a, b) if ha else (b, a)
    return 'cross' if min(h[0][0], h[1][0]) < v[0][0] < max(h[0][0], h[1][0]) and min(v[0][1], v[1][1]) < h[0][1] < max(v[0][1], v[1][1]) else ''


def _in_box(p, q, box):
    """The segment p-q passes through the inside of box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    if p[1] == q[1]: return y0 < p[1] < y1 and min(p[0], q[0]) < x1 and max(p[0], q[0]) > x0
    return x0 < p[0] < x1 and min(p[1], q[1]) < y1 and max(p[1], q[1]) > y0


def check(spec, canon=str):
    """Everything wrong with the circuit, as sentences that say what to change (empty when it can be printed)."""
    nodes, parts, lines, bodies = _layout(spec, canon)
    errs, ground, terms = [], [canon(g) for g in spec.get('ground') or []], {canon(k) for k in (spec.get('terminals') or {})}
    degree = {n: 0 for n in nodes}
    for _, _, ns, _, _ in parts:
        for n in ns: degree[n] += 1
    fmt = lambda pt: f'[{pt[0]:g}, {pt[1]:g}]'
    for who, p, q, (a, b) in lines:
        if p == q: errs.append(f'{who} starts and ends at the same point {fmt(p)}')
        elif p[0] != q[0] and p[1] != q[1]:                    # usually SPICE habit: every grounded part joined to one node "0" wherever it is
            hub, end = (b, a) if degree[b] >= degree[a] else (a, b)
            errs.append(f'{who} slants from {a} {fmt(p)} to {b} {fmt(q)}: every line is straight and a node is one point, so end it at a new '
                        f'node at {fmt((nodes[end][0], nodes[hub][1]))} and join that node to {hub!r} with a wire (a ground or return rail is a row of nodes joined by wires)')
    straight = [(w, p, q, ns) for w, p, q, ns in lines if p != q and (p[0] == q[0] or p[1] == q[1])]
    at = {}
    for n, pt in nodes.items():
        if pt in at: errs.append(f'nodes {at[pt]!r} and {n!r} are both at {fmt(pt)}: use one node')
        at[pt] = n
    for w, p, q, _ in straight:                                 # wires were split at the nodes they cross: only parts are left
        for n, pt in nodes.items():
            if _on(pt, p, q): errs.append(f'{w} runs over node {n!r} at {fmt(pt)}: a part cannot pass through a node; end it before the node and continue with a wire, or move the node')
    for i, (w1, p, q, ns1) in enumerate(straight):
        for w2, r, s, ns2 in straight[i + 1:]:
            how = _meets((p, q), (r, s))
            if how == 'overlap' and set(ns1) == set(ns2):     # parallel parts written on the same two nodes, as SPICE does
                d = (1, 0) if p[0] == q[0] else (0, -1)
                u, v = (r[0] + d[0], r[1] + d[1]), (s[0] + d[0], s[1] + d[1])
                errs.append(f'{w1} and {w2} both join {ns2[0]!r} and {ns2[1]!r}, so they would be drawn on one line: draw {w2} beside {w1}, '
                            f'between new nodes at {fmt(u)} and {fmt(v)} joined to {ns2[0]!r} and {ns2[1]!r} by wires')
            elif how == 'overlap': errs.append(f'{w1} and {w2} lie on top of each other: move one to its own row or column')
            elif how == 'cross': errs.append(f'{w1} crosses {w2}: move a node so that no lines cross')
        for name, (x0, y0, x1, y1), pins in bodies:          # other lines keep a little away from a symbol; its own pins' wires may run beside it
            m = 0 if p in pins or q in pins else 0.15
            if _in_box(p, q, (x0 - m, y0 - m, x1 + m, y1 + m)): errs.append(f'{w1} runs through the symbol of {name}: route it round (the body spans x {x0:g} to {x1:g}, y {y0:g} to {y1:g})')
    for n, k in degree.items():
        if k == 0: errs.append(f'node {n!r} is not used by any part: remove it')
        elif k == 1 and n not in terms and n not in ground: errs.append(f'node {n!r} is joined to one part only, so that part is left open: connect it, or list it in "terminals" if it is an open terminal')
    errs += [f'"terminals" names node {t!r}, which is not in the circuit' for t in terms if t not in nodes]
    for g in ground:
        if g not in nodes: errs.append(f'ground node {g!r} is not in "nodes"')
        elif any(nodes[g] in (p, q) and min(p[1], q[1]) < nodes[g][1] for _, p, q, _ in straight): errs.append(f'node {g!r} has a line going down, so its ground symbol would sit on it: ground a node with nothing below it')
    net = {n: n for n in nodes}                                   # nets joined by wires: a part with both ends in one net is shorted
    def root(n):
        while net[n] != n: n = net[n]
        return n
    for _, typ, ns, _, _ in parts:
        if typ == 'W': net[root(ns[0])] = root(ns[1])
    errs += [f'{name} is shorted: wires join both its ends, so no current flows through it' for name, typ, ns, _, _ in parts if typ in TWO and typ != 'W' and root(ns[0]) == root(ns[1])]
    for _, _, ns, _, _ in parts:                                  # one connected circuit (a transformer's two sides count as joined)
        for n in ns[1:]: net[root(n)] = root(ns[0])
    pieces = {root(n) for n in nodes}
    if len(pieces) > 1: errs.append(f'the circuit is in {len(pieces)} separate pieces: join them')
    return list(dict.fromkeys(errs))


def _side(p, q, half, text, obstacles, centre):
    """Which side of the part p-q its label goes on: the one whose label box hits fewer lines, bodies and labels (then the outer side)."""
    lines = str(text).split('\n')
    w, h = (0.19 * max(len(t) for t in lines) + 0.1) / G, 0.34 * len(lines) / G       # drawing units to grid steps
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    if p[1] == q[1]:
        cands = [((0, 1), (mx - w / 2, my + half, mx + w / 2, my + half + h)), ((0, -1), (mx - w / 2, my - half - h, mx + w / 2, my - half))]
    else:
        cands = [((1, 0), (mx + half, my - h / 2, mx + half + w, my + h / 2)), ((-1, 0), (mx - half - w, my - h / 2, mx - half, my + h / 2))]
    hits = lambda b: sum(b[0] < x1 and x0 < b[2] and b[1] < y1 and y0 < b[3] for x0, y0, x1, y1 in obstacles)
    outer = lambda s: (mx - centre[0]) * s[0] + (my - centre[1]) * s[1]
    s, box = min(cands, key=lambda c: (hits(c[1]), -outer(c[0])))
    obstacles.append(box)
    return s


def _multi(d, typ, at, flip, label):
    """Draw a part with 3 or 4 pins, its leads ending on the grid points PINS gives."""
    x, y = at[0] * G, at[1] * G
    make = {'opamp': lambda: E.Opamp(leads=False).scale(1.2), 'xfmr': lambda: E.Transformer().scale(1.875),     # only the one drawn is made:
            'npn': lambda: E.BjtNpn(circle=True), 'pnp': lambda: E.BjtPnp(circle=True),                         # inside a Drawing, a new element
            'nmos': lambda: E.NFet().reverse(), 'pmos': lambda: E.PFet().reverse()}[typ]()                       # is added to it
    if flip and typ == 'opamp': make = make.flip()
    el = make.anchor('p2').at((x - 0.94, y - G)) if typ == 'xfmr' else make.anchor('center').at((x, y))
    if label: el = el.label(label, loc='bottom' if typ in ('opamp', 'xfmr') else 'right', color=INK, fontsize=10)
    d += el
    if typ == 'opamp': leads = ((el.in1, (x - G, el.in1[1])), (el.in2, (x - G, el.in2[1])), (el.out, (x + G, y)))
    elif typ == 'xfmr': leads = ((el.p1, (x - G, y + G)), (el.p2, (x - G, y - G)), (el.s1, (x + G, y + G)), (el.s2, (x + G, y - G)))
    else:
        gate, top, bottom = (getattr(el, a) for a in {'npn': ('base', 'collector', 'emitter'), 'pnp': ('base', 'emitter', 'collector'),
                                                      'nmos': ('gate', 'drain', 'source'), 'pmos': ('gate', 'source', 'drain')}[typ])
        leads = ((gate, (x - G, y)), (top, (x, y + G)), (bottom, (x, y - G)))
    for a, b in leads: d += E.Line().at(a).to(b)


def circuit(spec, out):
    """spec: {"nodes": {"a": [0, 2], "b": [3, 2], "g": [0, 0], ...},   grid points [x, y]: x to the right, y up, 1 = one grid step
          "parts": [[name, type, node, node, "label", {options}], ...],
          "ground": ["g"], "terminals": {"o": "V_o"}, "node_labels": {"b": "A"}}
    Draw it as a textbook schematic on a grid: every part and wire is a straight horizontal or vertical line between two nodes,
    wires (type "W", name "") join nodes where there is no part, and no lines cross. Node names: letters and digits (a, b, n1, g).
    A node is ONE point: every part joined to it ends exactly there. So a return or ground rail along the bottom is a row of nodes
    (g1 [0, 0], g2 [3, 0], g3 [6, 0]) joined by wires, each part ending at the node below it; two parts in parallel each get their
    own pair of nodes, side by side, joined by wires.
    The app adds the junction dots, checks the circuit and says exactly what to change (a part left open, a part shorted by a
    wire, a line running over a node or through another part).
    Types (the node order matters):
      R, C, L, Z (an impedance: a box, for complex Z = R + jX), Fuse, Lamp, SW (open switch), AM (ammeter), VM (voltmeter):
      either order;  W: a wire
      V (DC source), Vac (AC source), Bat (battery), Vdep (dependent voltage source, a diamond): the + node first
      I (current source), Idep (dependent current source, a diamond): the arrow points from the first node to the second
      D (diode), Zener, LED: the anode first
      opamp: in−, in+, out;  npn, pnp: base, collector, emitter;  nmos, pmos: gate, drain, source;  xfmr: p1, p2, s1, s2
    Label: written beside the part: a value ("4 Ω"), a name ("R₁"), both on two lines ("R₁\\n4 Ω"), or "" for none;
      left out, the part's name is written. A dependent source's label is its value ("2 V_x", "0.5 I_1").
    Options: {"current": "I₁", "into": node}: an arrow on the part pointing into that node (default: the second node);
             {"voltage": "V₁", "plus": node}: + V₁ − across the part (default: + at the first node).
    Parts with 3 or 4 pins take {"at": [x, y]} and the app places their pins (leave pin nodes out of "nodes"):
      opamp: in− [x−1, y+0.5], in+ [x−1, y−0.5], out [x+1, y]  ("flip": true puts in+ on top)
      npn, nmos: base/gate [x−1, y], collector/drain [x, y+1], emitter/source [x, y−1]
      pnp, pmos: base/gate [x−1, y], collector/drain [x, y−1], emitter/source [x, y+1]
      xfmr: p1 [x−1, y+1], p2 [x−1, y−1], s1 [x+1, y+1], s2 [x+1, y−1]
      Other lines keep out of the symbol: an opamp or xfmr fills x−0.9 to x+0.9, y−1 to y+1; a transistor x−0.5 to x+0.3, y−0.5 to y+0.5.
    "ground": nodes drawn with a ground symbol (nothing may leave them downwards): one at most, on the return rail, never one under
    every part; a closed loop needs none. "terminals": open terminals with their labels; a port (Thevenin, Norton, load) shows both
    of its terminals (a and b). "node_labels": a name written at a node. Spacing: a part needs 2 or 3 steps; at 1 step its label has no room."""
    from figures import text_label
    errs = check(spec, text_label)
    if errs: raise ValueError('; '.join(errs[:3]) + (f' (and {len(errs) - 3} more)' if len(errs) > 3 else ''))
    nodes, parts, lines, bodies = _layout(spec, text_label)
    brand()
    xs, ys = [p[0] for p in nodes.values()], [p[1] for p in nodes.values()]
    centre = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    pad = 0.08
    obstacles = [(min(p[0], q[0]) - pad, min(p[1], q[1]) - pad, max(p[0], q[0]) + pad, max(p[1], q[1]) + pad) for _, p, q, _ in lines] + [b for _, b, _ in bodies]
    S = lambda pt: (pt[0] * G, pt[1] * G)
    degree = {n: 0 for n in nodes}
    for _, _, ns, _, _ in parts:
        for n in ns: degree[n] += 1
    with schemdraw.Drawing(show=False) as d:
        d.config(color=PURPLE, fontsize=11, font='DejaVu Sans', lw=1.5)           # Poppins has no Greek (Ω, µ)
        for name, typ, ns, label, opts in parts:
            if typ in PINS: _multi(d, typ, opts['at'], opts.get('flip'), label); continue
            cls, half, backwards = TWO[typ]
            a, b = (ns[1], ns[0]) if backwards else (ns[0], ns[1])
            p, q = nodes[a], nodes[b]
            el = cls().endpoints(S(p), S(q))
            if typ != 'W':
                left = (p[1] - q[1], q[0] - p[0])                                     # schemdraw's "top" is left of the drawing direction
                loc = lambda s: 'top' if s[0] * left[0] + s[1] * left[1] > 0 else 'bottom'
                s = _side(p, q, half / G + 0.1, label or 'x', obstacles, centre)
                if label: el = el.label(label, loc=loc(s), color=INK)
                if opts.get('voltage'):
                    plus = text_label(str(opts.get('plus', ns[0])))
                    signs = ['+', str(opts['voltage']), '−'] if plus == a else ['−', str(opts['voltage']), '+']
                    el = el.label(signs, loc=loc((-s[0], -s[1])), color=INK)
            d += el
            if opts.get('current') and typ != 'W':
                into = text_label(str(opts.get('into', ns[1])))
                d += E.CurrentLabelInline(direction='out', start=into == a).at(el).label(str(opts['current']), color=INK, fontsize=10)
        for n, pt in nodes.items():
            if n in {text_label(t) for t in spec.get('terminals') or {}}: d += E.Dot(open=True).at(S(pt))
            elif degree[n] >= 3: d += E.Dot().at(S(pt))
        for g in spec.get('ground') or []: d += E.Ground().at(S(nodes[text_label(g)]))
        taken = [(p, q) for _, p, q, _ in lines]
        for _, (x0, y0, x1, y1), pins in bodies:          # a pin's lead runs into its part
            taken += [(pin, ((x0 + x1) / 2, pin[1]) if not x0 < pin[0] < x1 else (pin[0], (y0 + y1) / 2)) for pin in pins]
        free = lambda pt: next(((dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if not any((pt in (p, q)) and
                                ((q[0] - p[0]) * dx + (q[1] - p[1]) * dy) * (1 if pt == p else -1) > 0 for p, q in taken)), (1, 0))
        for key in ('terminals', 'node_labels'):
            for n, text in (spec.get(key) or {}).items():
                pt = nodes.get(text_label(n))
                if pt is None: raise ValueError(f'{key} names node {n!r}, which is not in the circuit')
                dx, dy = free(pt)
                d += E.Label().at((pt[0] * G + 0.25 * dx, pt[1] * G + 0.25 * dy)).label(str(text), color=INK, fontsize=11,
                     halign={1: 'left', -1: 'right'}.get(dx, 'center'), valign={1: 'bottom', -1: 'top'}.get(dy, 'center'))
    fig = d.draw(show=False)
    ISSUES.append(LBL.crowded(fig.getfig(), fig.ax))
    fig.save(out, dpi=DPI)
    return out

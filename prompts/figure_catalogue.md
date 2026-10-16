# Figure catalogue

Rule of thumb: **draw a figure wherever a GATE paper would show one, or a topper would sketch one
while solving.** Every computational worked example gets its figure (Gantt chart, SFD/BMD, circuit,
tree, plot...). Figures live in content JSON as blocks; `scripts/figures.py` draws them in the Edwisely
palette (purple #4D2A87, mid-purple #7B5CB8, gold #D9A400, teal #2E8B87) on a transparent background,
so they sit cleanly inside the lavender example boxes.

```json
{"type": "figure", "kind": "gantt", "spec": {...}, "title": "SRTF", "caption": "optional", "width": 0.8}
```
`title` prints above in purple (use it when several figures are compared); `width` is a fraction of
the available width (Gantt charts default to full width). The same object can go in a question as
`"figure": {"kind": ..., "spec": ...}` or in the answer key as `"solution_figure"`.
Preview any spec: `python3 scripts/figures.py <kind> spec.json out.png`.
See every kind once: `python3 scripts/figures.py --gallery /tmp/gallery` (the GALLERY dict in
figures.py holds a ready spec for each example below - copy and edit).

## Kinds and spec fields

| kind | key fields | notes |
|---|---|---|
| `gantt` | `segments: [[label, start, end]]` or `rows: [{title, segments}]`; `row_labels: "left"`; `colors`; `ticks` | labels `idle`, `stall`, `bubble`, `-` are drawn hatched; same label = same colour |
| `plot` | `curves: [{x,y} or {expr, range} or {param:[xexpr,yexpr], range}]` with `label, color, style, step, fill, markers, values`; `points`, `hlines`, `vlines`, `annotations`, `xlim/ylim`, `xticks/yticks`, `logx/logy`, `equal`, `grid`, `axes_at_zero`, `size` | expressions use numpy names: sin, exp, log10, sqrt, where, clip, heaviside, pi... |
| `bars` | `categories`, `series: [{name, values}]`, `stacked`, `horizontal`, `values` | DI charts |
| `graph` | `nodes: [id or {id,label,shape,fill,xlabel}]`, `edges: [[a,b,label] or {from,to,label,highlight,style,dir,constraint}]`, `directed`, `rankdir`, `engine`, `start`, `same_rank`, `node_shape` | graphviz; `highlight` = answer path / critical path / MST |
| `cells` | `rows: [{label, cells:[text or {text,fill,note}]}]`, `index` | arrays, frames, tables of state |
| `beam` | `length`, `supports: [{x,type: pin/roller/fixed/hinge}]`, `loads: point/udl/uvl/moment`, `dims`, `points` | pair with `plot` for SFD/BMD |
| `circuit` | `elements: [{el, dir, label, id, at, to, tox, toy, loc, length}]` | schemdraw element names (Resistor, Capacitor, Inductor, SourceV, SourceI, Diode, Opamp, Ground, Line, Dot...) |

Anything else (phasor diagrams, 3-D sketches, Smith charts, psychrometric charts, flow nets, contour
maps): write a matplotlib script that calls `figures.brand()` first and `figures.save(fig, path)`,
then use an `image` block with that path. Keep the palette and font so it matches.

## What to draw, by GATE paper

**All papers - General Aptitude:** `bars`/`plot` for data interpretation (bar, line, pie via custom),
`graph` for seating/ordering puzzles and family trees, custom matplotlib for spatial aptitude (paper
folding, mirror images, cube nets).

**All papers - Engineering Mathematics:** `plot` for function behaviour, maxima/minima, areas between
curves, regions of integration, ODE solution curves, probability densities and CDFs (shade the
asked probability with a `where(...)` curve and `fill`), regression lines with `points`; `cells` for
matrices only when a pattern must be seen (otherwise use a `table` block).

**CS / DA:** `gantt` (CPU/disk scheduling, pipelining with `row_labels: "left"` and stalls), `cells`
(page replacement traces, cache sets, memory frames, stack/queue, hashing, arrays, bit fields),
`graph` (BST/AVL/heaps, traversals, graph algorithms with highlighted MST/shortest path, DFA/NFA/PDA
with `start` and `doublecircle`, precedence/conflict graphs, RAG/wait-for graphs, ER sketches, DAGs,
decision trees), `plot` (asymptotic growth, activation/loss curves, decision boundaries, distributions),
`bars` (DA: histograms, class counts).

**CE:** `beam` + `plot` (SFD/BMD/deflection, ILDs), `plot` (Mohr's circle via `param`, stress-strain,
hydrographs, unit/S-curve hydrographs, mass curves, consolidation e-log p, compaction curves,
speed-flow-density, grading curves with `logx`), `graph` (CPM/PERT networks with critical path
highlighted, pipe networks, trip distribution zones), `gantt` (construction bar charts), custom
(flow nets, retaining-wall pressure diagrams, cross-sections, traverse plots, curves in surveying).

**ME / PI / XE:** `beam` + `plot` (SFD/BMD), `plot` (Mohr's circle, P-v and T-s cycles via point
lists, vibration responses, cam displacement, S-N curves, EOQ cost curves, control charts), `graph`
(mechanisms as linkage sketches, block diagrams, project networks), `gantt` (scheduling/sequencing
- Johnson's rule), custom (velocity polygons, free-body diagrams of trusses/frames, heat exchanger
temperature profiles).

**EE / EC / IN:** `circuit` (DC/AC networks, RC/RL transients, diode/BJT/MOSFET/op-amp circuits,
bridges), `plot` (waveforms, transients, Bode magnitude/phase with `logx`, root-locus sketches via
points, Nyquist via `param`, transfer characteristics, constellation points, spectra, B-H curves,
torque-speed and V-curves), `graph` (control block diagrams, signal-flow graphs, state machines,
logic of sequential circuits), `cells` (K-maps as a 4 × 4 grid, truth/state tables, registers,
memory maps), `plot` with `step: true` curves for digital timing diagrams (one curve per signal, offset vertically).

**CH / BT / others:** `plot` (concentration-time, conversion, McCabe-Thiele with the 45° line and
staircase as a `step` curve, growth curves, Michaelis-Menten and Lineweaver-Burk lines, phase
diagrams), `graph` (process flow and reaction-network block diagrams, metabolic pathways),
`bars` (yields, compositions).

## Quality bar
- Labels match the text exactly (P1, A-B, q0, R1); units on axes; key values annotated
  (completion times, max BM, corner frequency, critical path).
- One idea per figure; a comparison of methods = one titled figure per method (as in
  `example_topic.json` section 2.11).
- After rendering, look at 2-3 pages as PNG: labels legible, nothing clipped, figure not taller
  than about half a page.

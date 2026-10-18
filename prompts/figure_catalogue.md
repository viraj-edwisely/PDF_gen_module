# Figures

Draw a figure wherever a GATE paper would show one, or a topper would sketch one while solving. Every computational
worked example of a visual topic gets its figure (Gantt chart, trace, tree, graph, circuit, beam, plot...).
The app draws figures from a JSON spec in the Edwisely palette:

{"type": "figure", "kind": "gantt", "spec": {...}, "title": "SRTF (optional)", "caption": "optional", "width": 0.8}

- "kind" is one of: gantt (or timeline), plot, bars, graph, cells, beam, circuit. Nothing else exists, and there are no image files.
- "spec" follows EXACTLY the spec of its kind below: the field names, the list shapes ([label, start, end]), and the value types. A figure whose spec is wrong cannot be drawn and is sent back to you.
- "width" is a fraction of the available width (Gantt charts default to the full width).
- In a question: "figure": {"kind": ..., "spec": ...}; in the answer key: "solution_figure": {...}.
- Labels match the text exactly (P1, A-B, q0, R1); units on axes; key values annotated. One idea per figure; keep labels short (under about 20 characters per node or cell).
- Labels are plain text: write Greek letters and subscripts as characters (ω, π, θ, x₀, T₁), or put maths inside $...$ ("$X(j\omega)$"). Never write \omega or \frac without $...$.
- A curve that follows a formula (exponential, sinc, sine, parabola) is an "expr" with a "range", never a short list of points: points are joined by straight lines. Point lists are for straight-line shapes (pulses, triangles) and measured data.
- Annotations sit inside the plot area (their "xytext" within the axis limits); the legend sits above the plot.
- Pick the kind by what the figure shows. graph is only for nodes joined by edges (trees, state machines, networks, block diagrams); it is never a way to draw a signal, a spectrum or a shape. Signals, spectra and impulse trains are plot figures (impulses: a curve with "stem": true); shafts, beams and loads are beam figures.
- Draw a figure only when it shows something the text does not: a figure that only repeats a formula or a number is left out.

## What to draw, by GATE paper
**General Aptitude:** bars/plot for data interpretation; graph for seating/ordering puzzles and family trees.
**Engineering Mathematics:** plot for function behaviour, maxima/minima, areas, regions, probability densities (shade with a where(...) curve and fill); cells for a matrix only when a pattern must be seen (otherwise a table block).
**CS / DA:** gantt (CPU/disk scheduling, pipelining with row_labels "left" and stalls, timelines of states), cells (page-replacement traces, cache sets, memory frames, stack/queue, hashing, arrays, registers, instruction formats as bit fields), graph (BST/AVL/heaps, traversals, graph algorithms with a highlighted MST or shortest path, DFA/NFA/PDA with start and doublecircle, precedence/conflict graphs, RAG/wait-for graphs, DAGs, memory/pointer chains for addressing modes), plot (asymptotic growth, decision boundaries, distributions), bars (histograms).
**CE:** beam + plot (SFD/BMD/deflection, ILDs), plot (Mohr's circle via param, stress-strain, hydrographs, consolidation, grading curves with logx), graph (CPM/PERT networks with the critical path highlighted), gantt (construction bar charts).
**ME / PI / XE:** beam + plot (SFD/BMD), plot (Mohr's circle, cycles from point lists, vibration responses, cam displacement, EOQ curves, control charts), graph (block diagrams, project networks), gantt (Johnson's rule sequencing).
**EE / EC / IN:** circuit (DC/AC networks, RC/RL transients, diode/BJT/MOSFET/op-amp circuits), plot (waveforms, transients, Bode with logx, Nyquist via param, transfer characteristics, step curves for digital timing diagrams), graph (control block diagrams, signal-flow graphs, state machines), cells (K-maps as a 4 x 4 grid, truth/state tables, registers, memory maps).
**CH / BT / others:** plot (concentration-time, conversion, McCabe-Thiele with a step curve, growth curves), graph (process-flow and reaction-network block diagrams), bars (yields, compositions).

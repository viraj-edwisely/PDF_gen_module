# Figures

The app draws every figure from a JSON spec in the Edwisely style, places the labels so they never overlap, and checks
that it draws. A figure that cannot be drawn, or whose labels still collide, is sent back to you.

{"type": "figure", "kind": "beam", "spec": {...}, "title": "SFD and BMD (optional)", "caption": "what to read off it", "width": 0.9}

- "kind" is one of the kinds in the reference below. "spec" follows that kind's spec EXACTLY: field names, list shapes, value types.
- In a question: "figure": {"kind": ..., "spec": ...}; in the answer key: "solution_figure": {...}.
- The caption says what the student reads off the figure (a value, a crossing, a direction), in one sentence.
- Labels are short: a symbol, a value or 1 to 4 words ("O", "H = 1800 m", "top image"). Never a sentence in a label:
  explanations go in the caption. Label only what the text or the example uses; a figure with 4 clear labels beats one
  with 12.
- Never write sentences about how a figure is drawn ("schematic", "drawn at separate positions", "not to scale" is added by
  the app where needed). A figure that needs an apology is the wrong figure: choose the right kind instead.

## Which kind: in this order
1. **Computed from physics** when the concept has one: the app computes the shape, so it is always right.
   beam (+ "diagrams": SFD/BMD), mohr, pressure (hydrostatic force on a plate), waveform (modulation, ASK/FSK/PSK),
   spectrum (AM, DSB-SC, SSB, line spectra), mccabe (McCabe-Thiele stage diagram: operating lines, q-line, numbered stages), vle (Txy and xy of a binary from Antoine constants),
   cycle (P-V, T-s, p-h: ideal gas, steam, refrigerants), control (step, Bode,
   Nyquist, root locus). Give the numbers of the example; never work out the curve yourself and draw it as a plot.
2. **Structured drawing**: process (flowsheets of equipment joined by streams), geometry (anything with real positions and proportions: bodies, plates, traverses, free-body
   diagrams, trusses, velocity triangles, floating bodies), block (signal and control block diagrams), circuit,
   logic (gates from a Boolean expression, K-maps, timing diagrams), graph (trees, automata, networks), cells (arrays,
   memory, traces, registers), gantt (schedules, pipelines), bars (data), plot (a function, data, a distribution).
3. **mermaid**: flowcharts of procedures and decision rules, concept maps, state diagrams, sequence diagrams (protocols),
   ER and class diagrams, timelines.
4. **illustration** (last resort): a picture of REAL apparatus or a cut-away that a student must recognise and that no kind above can
   draw (a four-stroke engine, a centrifugal pump, a Pelton wheel, a Francis turbine, a lathe, a shaper, a casting mould and its gating,
   a welding set-up, a metacentric-height apparatus, tray types in a column, a heat-exchanger cut-away, a waveguide, a dish antenna).
   Never for flowsheets (process), graphs, circuits, block diagrams or anything with values or scales. Use a stable "concept" key
   (four_stroke_si_engine) so every PDF gets the same picture, name every part in "parts" (the app draws the numbers on it), and look
   at the illustration library listed in the section prompt first: reuse a listed concept before asking for a new one, and ask for a
   new one only when the prompt says new pictures are allowed.
A plot shows the behaviour the student must see, so choose its range for that: a function with a singularity or a pole (1/x, ln x, tan x)
or a limit at infinity starts clear of the singularity (x from 0.5 or 1, not 0.01) so no spike swamps the rest, and uses a log axis when
the values span decades. The caption says what to read off the figure, never how its range was chosen ("the plot starts at positive x").
plot is only for a graph: both axes are real quantities with units, and the student reads a value off a curve. Anything
you would sketch on the board (a camera and its rays, a photograph and the ground, footprints, a tank, a body, a beam
of light, a layout) is geometry, with no axes, and dim items for the lengths. A plot whose axes would be "schematic", or
whose points all lie on one line, is the wrong kind and is sent back.
Never draw a physical body or a signal chain with plot or graph, never a spectrum or waveform with graph, and never put
two signals on one set of axes when the student must compare them: use stacked "panels" (plot) or waveform.

## The standard figure for common concepts
Use the figure a textbook uses: students recognise it and SMEs expect it.

**EC / EE / IN**
- AM: waveform (μ < 1, = 1, > 1) + spectrum + block diagrams of the modulator (square-law or switching) and the detector;
  envelope detector as a circuit (diode, RC). DSB-SC, SSB, VSB: waveform/spectrum + block diagram (product modulator,
  coherent detector with a local oscillator). FM/PM: waveform + spectrum (Carson bandwidth marked).
- Digital modulation: the bit train with the ASK/FSK/PSK waveforms (waveform), then the constellation (geometry with
  "axes": true, points and decision boundaries).
- Sampling and quantisation: plot panels (signal, samples as stems, reconstruction). Line codes: plot with "step".
- Control: block diagram of the loop (block, with feedback), step response, Bode, Nyquist, root locus (control).
- Circuits: circuit; diode/transistor characteristics: plot; logic: logic (gates, K-map, timing).
- Machines and power: phasor diagram (geometry arrows), equivalent circuit (circuit), torque-speed or efficiency curve (plot).

**ME / PI / XE / CE**
- Beams: beam with "diagrams": ["sfd", "bmd"]. Stresses: mohr; a stress element as geometry (a square with arrows).
- Hydrostatic force on a plate: pressure. Buoyancy and stability: geometry (body upright and heeled, with G, B, B′, M,
  weight and buoyancy arrows). Manometers: geometry (tube, fluid levels, depths as dims).
- Thermodynamic cycles: cycle (Otto, Diesel, Dual, Brayton on p-v and T-s; Rankine on T-s with the dome; vapour
  compression on p-h and T-s). Processes of a closed system: cycle or plot of the p-V path with the work area filled.
- Mechanisms, kinematics, velocity triangles (turbines, pumps): geometry. Vibration responses: plot.
- Process flow and flowsheets (distillation column with condenser and reboiler, flash drum, reactor with recycle, heat exchanger,
  pump circuit, steam still, extractive or azeotropic distillation with solvent recovery): process, with the main flow on one row
  and recycles on the row above or below. Never block (a signal chain) or plot. Stream labels are short (a symbol or one or two
  words: F, D, B, L, V, Steam, Reflux); a stream between neighbouring pieces of equipment has room for about 8 letters.
- Stage-by-stage design of a binary column (number of stages, feed stage, reflux): mccabe, computed from alpha (or an
  equilibrium table), xD, xF, xB, q and R. Take the stage count and feed stage in your text from the same inputs (the figure's
  title shows what they compute). Txy and xy diagrams of a binary (boiling-point diagram, flash notes): vle, from the Antoine constants of the two
  components (never a hand-drawn curve through a few points).
- Surveying: geometry with bearing items and "north": true. Photogrammetry: geometry - the camera station O, the photo
  plane as a short segment at distance f, rays to the ground as dashed segments, the ground and datum, with H, h and f
  as dims; relief displacement with the principal point, the base and top images and d as a dim; stereo pairs with
  both stations, the air base B as a dim and the rays to G and T; overlap as translucent rects (one per photograph)
  with the advance a and strip spacing b as dims. Soil mechanics curves (grading, consolidation): plot ("logx").
- Project networks: graph with the critical path highlighted. Construction schedules: gantt.

**CS / DA**
- Scheduling and pipelines: gantt. Page replacement, caches, memory, stacks, hashing, arrays: cells.
- Trees, graphs, automata, precedence and wait-for graphs: graph. Algorithms and procedures: mermaid flowchart.
- Protocols and message exchanges: mermaid sequenceDiagram. ER models: mermaid erDiagram. Growth of functions: plot.

**Engineering Mathematics / General Aptitude**
- Function behaviour, areas, distributions with shaded probabilities: plot. Data interpretation: bars or plot.
- Seating and ordering puzzles, family trees: graph.

## Figure rules
- Labels match the text exactly (P1, A-B, q0, R1, G, B′); units on axes; the key value of the figure labelled.
- Labels are plain text: Greek letters and sub/superscripts as characters (ω, π, θ, x₀, m³) or simple maths inside $...$.
- A curve that follows a formula is an "expr" with a "range", never a few points (points are joined by straight lines).
- Frequencies in waveforms are illustrative (carrier 10 to 20 times the message); the example's own numbers go in the text.
- One idea per figure; a figure inside a worked example uses that example's numbers.

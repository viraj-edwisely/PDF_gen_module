# Topic content JSON

The app assembles the PDF from the parts each task asks for. Section order in the PDF: cover and "What you will learn" →
Contents → Concept notes → Common GATE traps → Revision card → Previous-year GATE questions → Practice questions →
Sample paper → Answer key and solutions.

## Notes: a list of sections
{"heading": "short section title (numbered 2.1, 2.2 ... automatically)", "blocks": [ BLOCK, ... ]}
Add "no_example": true only for a pure-definition section that cannot have a worked example.

## BLOCK types (use exactly these field names)
A bare string in a blocks list is a `para`.

| type | fields | renders as |
|---|---|---|
| `para` | text | paragraph |
| `subhead` | text | bold run-in heading ("Order P1, P2, P3:", "(a) Non-pre-emptive") |
| `bullets` / `numbered` | items: [string, ...] | list |
| `formula` | latex (no $), key (bool), where: [[symbol, meaning, unit], ...] | display maths. `key: true` frames it as one of the 1-3 formulas of the section to remember. `where` lists the symbols it introduces, one row each, shown under it (a symbol already explained earlier in the section is left out by the app, so list every new one) |
| `table` | header: [string, ...], rows: [[string, ...], ...], total_row (bool, optional: last row bold) | purple-header table |
| `example` | title, problem, given, find, steps, answer, rushed, check | worked-example box (see WORKED EXAMPLES below) |
| `trap` | text, title (optional, default "Common GATE trap") | box: a mistake GATE questions are built to catch |
| `note` | text, title (optional), blocks (optional) | box for GATE habits and conventions |
| `callout` | text | purple box: the one rule to remember |
| `code` | text | monospace box (C code, pseudo-code, SQL, assembly). Text is shown exactly as typed, no maths |
| `figure` | kind, spec, title (optional), caption (optional), width (0 to 1, optional) | a figure drawn by the app; see FIGURES for every kind and its exact spec |

The example "title" is the topic of the example only ("Relative branch target"), without the words "Worked example".
There are no image blocks: every picture is a `figure` the app draws.
Do not write a Symbol / Meaning / Unit table: put the symbols in the formula's `where`.

## WORKED EXAMPLES
{"type": "example", "title": "Moving, heated closed system",
 "problem": "A closed 20 kg body ... Find the change in internal energy.",      (a string, or a list of BLOCKs with its figure)
 "given": [["m", "20 kg"], ["V_1", "5 m/s"], ["Q", "+50 kJ"]],                   (symbol and value with unit; optional for conceptual examples)
 "find": "$\Delta U$",
 "steps": [{"say": "Kinetic-energy change", "latex": "\Delta KE = \frac{1}{2}(20)(15^2 - 5^2) = 2000\ \mathrm{J}", "result": "2.000 kJ"},
           {"say": "Energy balance", "latex": "\Delta U = Q - W - \Delta KE - \Delta PE", "text": "optional short sentence", "result": "35.61 kJ"}],
 "answer": "ΔU = 35.61 kJ",
 "rushed": "Using only Q − W gives 38 kJ: it puts the energy that went into speed and height into internal energy.",
 "check": {"expr": "50 - 12 - 0.5*20*(15**2-5**2)/1000 - 20*9.81*2/1000", "answer": "35.61"}}
- One step per line of working a student writes: "say" names what the step finds (a few words), "latex" is the working
  as one display line (no $), "result" its value with unit. A step may hold "blocks" (a table or the figure it needs).
- 3 to 6 steps for a numerical example; never one paragraph of working.
- "rushed": the answer a hurried student reaches and why it is wrong, in one or two sentences (leave it out if there is none).

## "check": how the app verifies numbers
Write the check from the values given in the problem or question (never from rounded intermediate values), with exact constants (2*pi*N/60, not 9550). Every value it uses must be stated in the problem or question text.
A worked example with a numeric result, and every NAT question, carry a "check":
- example: "check": {"expr": "0x3000 - 0x1F4", "answer": "0x2E0C"}   (answer = the final result as written in the solution)
- NAT question: "check": "0.40*ceil(1.05/0.40)"   (must give the "answer", within "answer_range")
- MCQ whose correct option is a number: "check": "4500 - 200"   (must give the number in the correct option)
"expr" is plain arithmetic on the numbers of the problem: + - * / // % **, parentheses, hex literals like 0x1F4, and only these functions:
ceil, floor, round, sqrt, log, log2, log10, exp, sin, cos, tan, abs, min, max, int, float. No variables, no units, no text.
Leave "check" out for questions whose answer is not a number.

## QUESTION fields
`question`, `qtype` (MCQ/MSQ/NAT), `marks` (1 or 2), `options` (exactly 4 strings, without "(A)" prefixes; omit for NAT),
`answer` (letter(s) "B" / "A, C", or the number for NAT), `answer_range` (NAT, e.g. "7.19 to 7.21"),
`steps` (the solution in the answer key, 2 to 4 steps as in WORKED EXAMPLES; a short string `solution` only for a one-line
conceptual answer), `check` (see above), `level` (practice only: Easy/Medium/Hard),
`figure` (a figure object {kind, spec, width} drawn under the question; the question then says "shown in the figure"),
`solution_figure` (a figure object shown in the answer key), `mirrors` (internal: the GATE archetype it is calibrated to; never printed).
PYQs only: `source` like CS-GATE-2019.

## Text markup
`**bold**`, `*italic*`, inline maths `$...$` (see MATHS), a blank line starts a new paragraph, `\$` is a literal dollar.
Units are plain text with their characters: m³, kg/m³, m/s², N·m, kN·m, °C, Ω, µF (never m$^3$ or m^3).

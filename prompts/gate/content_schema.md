# Topic content JSON (input to scripts/build_topic_pdf.py)

Two complete, rendered examples - copy their structure:
- `example_topic.json` - CS · Operating System · CPU Scheduling Algorithms (the reference depth:
  11 sections, 11 worked examples, 18 figures, traps, comparison section, 5 PYQs, 10 practice, sample paper).
- `example_topic_figures_ce.json` - CE · SFD and BMD (beam diagrams, SFD/BMD plots, a figure inside a
  practice question). It has no PYQs only because no PYQ bank was attached when it was made.

IDs and `exam` are used only for file names / INDEX.xlsx; they are never printed in the PDF.
GATE-level rules for every field: `gate_level_standard.md`. Check with `scripts/check_gate_level.py`.

```json
{
  "paper": "CS", "exam": "GATE 2027", "subject": "Operating System",
  "module_id": "CS-M21", "module_name": "Operating System I",
  "topic_id": "CS-S10-T05", "topic_name": "CPU Scheduling Algorithms",
  "syllabus_line": "exact line from the official GATE syllabus",
  "subtitle": "optional cover subtitle",
  "contents": true,                     // clickable contents page after the cover (default true)
  "objectives": ["3-5 outcomes, verb first"],
  "prerequisites": ["topic name only"],
  "notes": [ {"heading": "Section title (numbered automatically 2.1, 2.2 ...)", "blocks": [ BLOCK, ... ],
              "no_example": false} ],
  "traps": ["5-10 one-line GATE traps, **bold lead-in:** explanation"],
  "revision_card": ["5-8 one-line key points / formulas"],
  "pyqs": [ QUESTION, ... ],            // official only, source in capitals: CS-GATE-2019
  "practice": [ QUESTION, ... ],        // original, 10-12, level Easy -> Medium -> Hard
  "sample_paper": {"title": "Sample paper (timed)", "duration": "12 min", "marks": 8, "questions": [ QUESTION, ... ]}
}
```
Section order in the PDF: cover + What you will learn → Contents (clickable, page 2) → Concept notes → Common GATE traps → Revision card →
Previous-year GATE questions → Practice questions → Sample paper → Answer key and solutions.

## BLOCK types
A bare string in a blocks list is a `para`.

| type | fields | renders as |
|---|---|---|
| `para` | text | paragraph |
| `subhead` | text | bold run-in heading ("Order P1, P2, P3:", "(a) Non-pre-emptive") |
| `bullets` / `numbered` | items[] | list |
| `formula` | latex (no $) | centred display maths |
| `table` | header[], rows[][], widths[] (pt, optional), total_row (bool: last row bold, shaded - Average/Total) | purple-header striped table |
| `example` | title, problem, solution - each a **string** (blank line = new paragraph) **or a list of BLOCKs** (tables, figures, subheads, formulas) | lavender worked-example box that can run across pages |
| `trap` | text, title (default "Common GATE trap") | titled lavender box - a mistake GATE questions are built to catch |
| `note` | text, optional title, optional blocks | lavender box with purple bar (GATE habits, conventions) |
| `callout` | text | purple box, white text (the one rule to remember) |
| `code` | text | monospace box (C code, pseudo-code, SQL) |
| `figure` | kind, spec, title, caption, width (0-1) | brand-styled figure drawn by figures.py - see `figure_catalogue.md` |
| `image` | path, title, caption, width | a PNG (PYQ figure crop, custom matplotlib figure) |
| `spacer` / `pagebreak` | height | layout control, rarely needed |

## QUESTION fields
`question`, `qtype` (MCQ/MSQ/NAT), `marks` (1/2), `options` (exactly 4 strings; omit for NAT),
`answer` (letter(s) "B" / "A, C", or the number for NAT), `answer_range` (NAT: "7.19 to 7.21"),
`solution` (string or BLOCK list, shown in the answer key), `source` (PYQs only, e.g. `CS-GATE-2016`),
`level` (practice only: Easy/Medium/Hard), `figure` ({kind, spec, width} drawn under the stem) or
`image` (path, e.g. PYQ crop), `solution_figure` ({kind, spec}) or `solution_image`,
`mirrors` (internal: the PYQ archetype an original question is calibrated to; never printed).

## Text markup
`**bold**`, `*italic*`, inline maths `$...$` (matplotlib mathtext: `\frac{a}{b}`, `\Theta(n\log n)`,
`x^{2}`, `\sum_{i=1}^{n}`, `\mathrm{text}`), `\n` line break, `\$` literal dollar.
Mathtext does not support `\begin{...}` environments - use a `table` block for matrices/truth tables.

# Non-GATE module content JSON

The app assembles the module from the parts each task asks for:
{"title", "description", "subject", "study_time", "audience", "topics": [{"title", "tagline", "blocks": [ BLOCK, ... ]}],
 "case_study", "practice", "revision"}  (case_study and revision may be null when the user leaves them out).

## BLOCK types (use exactly these field names)
| type | fields | renders as |
|---|---|---|
| `situation` | text | lavender box SITUATION: the real-world setup that opens a topic |
| `concept` | text | lavender box CONCEPT: the key idea, **bold** key terms |
| `worked_example` | text, title (optional), check (optional) | yellow box WORKED EXAMPLE: numbers worked through |
| `pitfall` | text | yellow box COMMON PITFALL |
| `note` | text | lavender box NOTE |
| `quick_check` | items: [{q, a}] | Q&A box at the end of a topic (2 questions) |
| `para` | text | plain paragraph (a bare string also works) |
| `table` | title (optional), header: [...], rows: [[...], ...] | purple-header table |
| `bullets` / `numbered` | items: [string, ...] | list |
| `formula` | latex (no $) | centred maths, one equation |
| `figure` | kind, spec, title, caption, width | a figure drawn by the app (see FIGURES) |
There are no image blocks.

A worked example with a numeric result has "check": {"expr": "plain arithmetic that recomputes the result", "answer": "the result as written"},
e.g. {"expr": "(120 - 100) / 100 * 100", "answer": "20"}. Allowed in expr: numbers, + - * / // % **, parentheses and
ceil, floor, round, sqrt, log, log2, log10, exp, abs, min, max. No variables, units or text.

Text markup: `**bold**`, `*italic*`, inline maths `$...$` (see MATHS), a blank line (`\n\n`) starts a new paragraph, `\$` is a literal dollar.

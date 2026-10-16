# Non-GATE module content JSON (input to render/render_nongate.py)

```json
{
  "title": "module title", "description": "2-3 sentences for the cover (under 350 characters)",
  "subject": "...", "study_time": "3-4 hours, self-paced", "audience": "who it is for",
  "topics": [ {"title": "...", "tagline": "one line", "blocks": [ BLOCK, ... ]} ],
  "case_study": {"title": "...", "subtitle": "...", "paragraphs": [{"lead": "Situation.", "text": "..."}], "discussion": "..."},
  "practice": [ {"tag": "Topic name · Application", "question": "...", "answer": "model answer"} ],
  "revision": {
    "concepts": [{"title": "01 · Topic", "points": ["..."]}],
    "distinctions": {"header": ["This", "vs. this", "Key difference"], "rows": [["...", "...", "..."]]},
    "mistakes": [{"title": "...", "text": "..."}],
    "checklist_title": "...", "checklist": ["..."]
  }
}
```
`case_study` and `revision` are optional. Every key shown in a list item is required.

## BLOCK types
| type | fields | renders as |
|---|---|---|
| `situation` | text | lavender box SITUATION: the real-world setup that opens a topic |
| `concept` | text | lavender box CONCEPT: the key idea, **bold** key terms |
| `worked_example` | text, optional title | yellow box WORKED EXAMPLE: numbers worked through |
| `pitfall` | text | yellow box COMMON PITFALL |
| `note` | text | lavender box NOTE |
| `quick_check` | items: [{q, a}] | Q&A box at the end of a topic (2 questions) |
| `para` | text | plain paragraph (a bare string also works) |
| `table` | title (optional), header[], rows[][] | purple-header table |
| `bullets` / `numbered` | items[] | list |
| `formula` | latex (no $) | centred maths |
| `figure` | kind, spec, caption, width | brand figure (see the figure catalogue) |

Text markup: `**bold**`, `*italic*`, inline maths `$...$`, a blank line (`\n\n`) starts a new paragraph.

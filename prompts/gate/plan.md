Plan the GATE topic PDF for "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Previous-year GATE questions already found for this topic (use their archetypes; may be empty):
{{PYQS}}

Return this JSON:
{
  "subtitle": "one line for the cover, e.g. Topic guide: concept notes, worked examples, previous-year GATE questions, practice and sample paper",
  "syllabus_line": "{{SYLLABUS}}",
  "objectives": ["3 to 5 outcomes, each starting with a verb"],
  "prerequisites": ["topic names only, no IDs"],
  "sections": [{"heading": "short descriptive title", "ideas": "the GATE-testable ideas this section covers", "example": "idea for its GATE-style worked example (a 2-mark-size problem)"}],
  "archetypes": ["the question types GATE asks on this topic; the notes and practice must cover every one"]
}

Rules
- Split the topic into 4 to 12 GATE-testable ideas (usually 5 to 8), one section each. Add a final comparison section ("one problem, every method") only if the topic has several methods.
- Headings are short: they become lines of the contents page.
- If the syllabus_line above is already a sentence, copy it exactly; if it is empty, write one line in the style of the official GATE syllabus for this topic.

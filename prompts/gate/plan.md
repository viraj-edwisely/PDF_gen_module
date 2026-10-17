Plan the GATE topic PDF for "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

User's instructions (follow them within the GATE format and the JSON below; "(none)" means none):
{{USER_PROMPT}}

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
  "sections": [{"heading": "short descriptive title", "ideas": "the GATE-testable ideas this section covers",
                "example": "its worked example: the archetype it trains, the data, what is asked, and the step a rushed student gets wrong",
                "figure": "kind: what it draws -> what the student reads off it (e.g. 'gantt: SRTF schedule of the example -> P2 is pre-empted at t = 3, so its waiting time has two parts'), or empty"}],
  "archetypes": ["the question types GATE asks on this topic; the notes and practice must cover every one"]
}

Rules
- Split the topic into 4 to 12 GATE-testable ideas (usually 5 to 8), one section each. Add a final comparison section ("one problem, every method") only if the topic has several methods.
- Headings are short: they become lines of the contents page.
- Every worked example is a GATE 2-mark-size problem of its own archetype: no two sections test the same skill, and none is a one-line substitution into a formula. Prefer the example a topper would choose to explain the idea: one with a twist (arrivals, a tie, a sign change, a non-standard support, a stepped section) that shows why the rule matters.
- A figure earns its place only if the student reads something off it that the text does not say as quickly (a waiting time, a peak, a crossing, a path, a stepped geometry). Write that in the "figure" field after "->". If you cannot, leave "figure" empty: no decorative figures, and no figure that only repeats a formula.
- Plan a figure for every section where GATE would show a diagram or a topper would sketch one (schedules, traces, trees, graphs, circuits, beams, plots, memory layouts, timelines, state tables). A numerical or visual topic needs figures in most sections. Use only the figure kinds listed in FIGURES.
- If the syllabus_line above is already a sentence, copy it exactly; if it is empty, write one line in the style of the official GATE syllabus for this topic.

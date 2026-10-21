Plan the GATE topic PDF for "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

Subtopics it must cover (each one gets a section): {{SUBTOPICS}}

User's instructions (follow them within the GATE format and the JSON below; "(none)" means none):
{{USER_PROMPT}}

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Pages of a reference handbook on this topic (may be "(none)"). Use them ONLY to check that "coverage" misses nothing
standard and which figures and derivations are standard for this topic. Never copy their text, examples or questions.
<reference>
{{REFERENCE}}
</reference>

Previous-year GATE questions already found for this topic (use their archetypes; may be empty):
{{PYQS}}

Return this JSON:
{
  "subtitle": "one line for the cover, e.g. Topic guide: concept notes, worked examples, previous-year GATE questions, practice and sample paper",
  "syllabus_line": "{{SYLLABUS}}",
  "objectives": ["3 to 5 outcomes, each starting with a verb"],
  "prerequisites": ["topic names only, no IDs"],
  "storyline": "3 to 5 sentences: how the sections build on each other, from what the idea is and why it matters, to how it works, how it is analysed, its variants, and how GATE tests it",
  "coverage": [{"subtopic": "each subtopic above, and each item of the syllabus line", "section": "the heading of the section that teaches it"}],
  "notation": [{"symbol": "μ", "meaning": "modulation index", "unit": "", "convention": "0 < μ ≤ 1 for envelope detection"}],
  "sections": [{"heading": "short descriptive title", "builds_on": "the heading of the earlier section this one needs, or empty",
                "ideas": "the ideas this section teaches, in the order taught",
                "example": "its worked example: the archetype it trains, the data, what is asked, and the step a rushed student gets wrong",
                "figure": "kind: what it draws -> what the student reads off it (e.g. 'beam with SFD/BMD: 6 m SSB with UDL -> maximum moment 45 kN·m at mid-span')",
                "no_figure_reason": "only when figure is empty: why a figure would add nothing"}],
  "archetypes": ["the question types GATE asks on this topic; the notes and practice must cover every one"]
}

Rules
- Order the sections as a storyline a teacher would follow at the board: what it is and why it matters, how it works or
  is built, how it is analysed (formulas), variants and limits, then how GATE combines them. Each section builds on an
  earlier one; for a system topic (a modulation scheme, a receiver, a control loop, a cycle, a process) the first section
  is an overview of the whole system with its block diagram.
- Every subtopic above and every item of the syllabus line appears in "coverage" with the section that teaches it.
  Nothing may be left out; nothing outside the syllabus line is added. As many sections as that needs (usually 4 to 12).
- No section repeats the formulas of an earlier one. A final "one problem, every method" section is allowed only when
  the topic has several methods, as a comparison, not a re-teaching.
- "notation": every symbol the PDF will use, once, with its unit and the sign convention GATE uses (heat into the system
  positive, tension positive, ...). All sections and questions use exactly these symbols.
- Headings are short: they become lines of the contents page.
- Every worked example is a GATE 2-mark-size problem of its own archetype: no two sections test the same skill, and none
  is a one-line substitution into a formula. Prefer the example a topper would choose: one with a twist that shows why
  the rule matters.
- Pick each figure from the standard figures in FIGURES (the figure a textbook uses for that concept), using the kind
  it names (a computed kind when there is one). Plan a figure for every section where GATE would show a diagram or a
  topper would sketch one; a numerical or visual topic needs one in almost every section. Leave "figure" empty only
  with a "no_figure_reason". No decorative figures.
- If the syllabus_line above is already a sentence, copy it exactly; if it is empty, write one line in the style of the
  official GATE syllabus for this topic.

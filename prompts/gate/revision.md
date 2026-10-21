Write the revision page of the GATE topic PDF "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}) from its concept notes, which are
summarised below section by section (heading, key formulas, rules and traps), in the order the student read them.

{{DIGEST}}

Return this JSON:
{"rows": [{"section": "the section heading, as given",
           "idea": "the idea in one plain sentence of at most 15 words",
           "formula": "its key formula as LaTeX without $ (empty if the section has none)",
           "rule": "the decision rule or condition the student applies in the exam, in one line",
           "trap": "the mistake GATE questions are built to catch here, in one line"}],
 "flow": ["4 to 8 short links that show how the ideas lead into each other, first section to last, each 'A -> B: why' in at most 12 words"]}

Rules
- One row per section above, in the same order, with the same headings. Nothing that is not in the notes.
- The idea is plain language a student can repeat aloud; the formula is copied from the notes, not rewritten.
- Every line is short: this page is read in the last ten minutes before the exam.
- Follow MATHS for the formulas.

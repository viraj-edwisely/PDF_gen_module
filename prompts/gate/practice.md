Write the practice questions for the GATE topic "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

GATE question archetypes for this topic: {{ARCHETYPES}}
Concepts covered in the notes (headings): {{HEADINGS}}
Previous-year questions already in the PDF (do NOT reuse or lightly change them):
{{PYQS}}

Return this JSON: {"practice": [ QUESTION, ... ]}  (QUESTION format: see the schema)

Requirements
- 10 to 12 questions, ordered Easy, then Medium, then Hard. Easy = GATE 1-mark, Hard = GATE 2-mark, Medium = 1 or 2 marks.
- Mix of MCQ, MSQ and NAT. Numerical topics: 30 to 50 percent NAT. At least one MSQ. At least a third are 2-mark.
- GATE phrasing: MCQ "Which one of the following is CORRECT?"; MSQ "Which of the following statements is/are CORRECT?"; NAT ends with "______" and states units and rounding ("rounded off to two decimal places"), with an "answer_range".
- MCQ distractors come from real mistakes (wrong convention, forgotten factor, missed idle time). Exactly four options, no "all/none of the above". Answers are letters ("B", "A, C").
- Every question has a "solution" of 2 to 4 lines of working that reaches the answer, and says why the tempting distractor is wrong when that is the point.
- Every question has an internal "mirrors" field naming the archetype it is calibrated to. Add a "figure" where GATE would show a diagram.
- Practice questions carry NO "source" field and never look like they are from a GATE paper.
- Compute every answer carefully.

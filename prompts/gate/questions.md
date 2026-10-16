Write all the questions and the closing material for the GATE topic "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

GATE question archetypes for this topic: {{ARCHETYPES}}
Concepts covered in the notes (headings): {{HEADINGS}}
Previous-year questions already in the PDF (do NOT reuse or lightly change them):
{{PYQS}}

Return this JSON:
{
  "practice": [ QUESTION, ... ],
  "sample_paper": {"title": "Sample paper (timed)", "duration": "12 min", "marks": 8, "questions": [ QUESTION, ... ]},
  "traps": [ "**bold lead-in:** explanation", ... ],
  "revision_card": [ "one-line key point", ... ]
}
(QUESTION format: see the schema.)

PRACTICE: 10 to 12 questions, ordered Easy, then Medium, then Hard. Easy = GATE 1-mark, Hard = GATE 2-mark, Medium = 1 or 2 marks. Mix of MCQ, MSQ and NAT (numerical topics: 30 to 50 percent NAT), at least one MSQ, at least a third 2-mark. Each has a "level" and carries NO "source" field.

SAMPLE PAPER: 5 questions totalling 8 marks for 12 minutes (for example 2 x 1-mark and 3 x 2-mark): a GATE-like mix of MCQ, MSQ and NAT. "marks" must equal the sum of the question marks. Every sample question must be DIFFERENT from every practice question. No "source" and no "level" field.

TRAPS: 5 to 10 one-line mistakes GATE questions are built to catch.
REVISION CARD: 5 to 8 one-line key points: formulas and decision rules to recall in the exam.

For every question
- GATE phrasing: MCQ "Which one of the following is CORRECT?"; MSQ "Which of the following statements is/are CORRECT?"; NAT ends with "______", states units and rounding ("rounded off to two decimal places") and has an "answer_range".
- MCQ distractors come from real mistakes (wrong convention, forgotten factor, missed idle time). Exactly four options, no "all/none of the above". Answers are letters ("B", "A, C").
- A "solution" of 2 to 4 lines of working that reaches the answer, saying why the tempting distractor is wrong when that is the point.
- An internal "mirrors" field naming the archetype it is calibrated to. Add a "figure" where GATE would show a diagram.
- Compute every answer carefully.

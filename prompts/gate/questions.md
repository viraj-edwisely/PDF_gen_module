Write all the questions and the closing material for the GATE topic "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

User's instructions (follow them within the GATE format and the JSON below; "(none)" means none):
{{USER_PROMPT}}

GATE question archetypes for this topic: {{ARCHETYPES}}
Concepts covered in the notes (headings): {{HEADINGS}}
Notation of the notes (use exactly these symbols, units and conventions): {{NOTATION}}
Previous-year questions already in the PDF (do NOT reuse or lightly change them):
{{PYQS}}

Return this JSON:
{
  "practice": [ QUESTION, ... ],
  "sample_paper": {"title": "Sample paper (timed)", "duration": "12 min", "questions": [ QUESTION, ... ]},
  "traps": [ "**bold lead-in:** explanation", ... ]
}
(QUESTION fields: see the schema.)

PRACTICE: 10 to 12 questions, ordered Easy, then Medium, then Hard. Easy = GATE 1-mark, Hard = GATE 2-mark, Medium = 1 or 2 marks. Mix of MCQ, MSQ and NAT (numerical topics: 30 to 50 percent NAT), at least one MSQ, at least a third 2-mark. Each has a "level" and carries NO "source" field.

SAMPLE PAPER: 5 questions totalling 8 marks (for example 2 x 1-mark and 3 x 2-mark): a GATE-like mix of MCQ, MSQ and NAT. Every sample question must be DIFFERENT from every practice question. No "source" and no "level" field.

TRAPS: 5 to 10 one-line mistakes GATE questions are built to catch.

For every question
- GATE phrasing: MCQ "Which one of the following is CORRECT?"; MSQ "Which of the following statements is/are CORRECT?"; NAT ends with "______", states units and rounding ("rounded off to two decimal places") and has an "answer_range" wide enough to accept the usual approximations (for example 9550 for 60000/2pi, or pi = 3.14).
- Exactly one defensible answer: state every assumption a careful student needs (word size, signed or unsigned, units, which convention).
- Every value the solution uses is stated in the question text with its unit (material constants such as G or E, lengths, allowed limits, diameters of each segment). A figure only illustrates: never leave data to the figure alone.
- MCQ distractors come from real mistakes (wrong convention, forgotten factor, missed idle time). Exactly four options, no "all/none of the above". Answers are letters ("B", "A, C").
- "steps": the solution as 2 to 4 numbered steps (WORKED EXAMPLES format: "say", one "latex" line of working, "result") that
  reach the answer; the last step's "text" says why the tempting distractor is wrong when that is the point. A purely
  conceptual question may use a one- or two-sentence "solution" instead.
- A "check" for every NAT question and for every MCQ whose correct option is a number (see the schema).
- Together the practice questions cover every archetype listed above; no two practice questions are the same problem with new numbers.
- An internal "mirrors" field naming the archetype it is calibrated to. Add a "figure" only where GATE would show a diagram (a beam, a circuit, a traverse, a graph to read): never one that only repeats the numbers already in the question.

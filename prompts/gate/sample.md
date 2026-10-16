Write the timed sample paper for the GATE topic "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

GATE question archetypes for this topic: {{ARCHETYPES}}
Practice questions already written (the sample paper must be DIFFERENT from all of them):
{{PRACTICE_STEMS}}

Return this JSON:
{"sample_paper": {"title": "Sample paper (timed)", "duration": "12 min", "marks": 8, "questions": [ QUESTION, ... ]}}

Requirements
- 5 questions totalling 8 marks, for 12 minutes: a GATE-like mix of MCQ, MSQ and NAT, with 1-mark and 2-mark questions (for example 2 x 1-mark and 3 x 2-mark). "marks" must equal the sum of the question marks.
- Same GATE phrasing, option and NAT rules as the practice questions. Original questions, each with an answer, a 2 to 4 line "solution" and an internal "mirrors" field. No "source" and no "level" field.
- Compute every answer carefully.

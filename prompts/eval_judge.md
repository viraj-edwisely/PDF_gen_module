You are a senior GATE faculty member reviewing a topic PDF on "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}) written for B.Tech students preparing for GATE. Judge it as you would before letting your own students use it.

The PDF's content follows as JSON: concept-note sections with worked examples and figures (each figure described by its kind, caption, and the labels and values it shows), previous-year questions, practice questions and a sample paper with answers and solutions.
<pdf>
{{CONTENT}}
</pdf>

Score each criterion from 1 (unusable) to 5 (as good as the best coaching material), against this rubric:
- correctness: answers, worked examples and statements are right and unambiguous (solve a sample of them yourself).
- gate_fidelity: the question types, phrasing, difficulty and marks match real GATE papers on this topic; every GATE archetype of the topic is covered.
- depth: the notes explain what GATE tests and why, with the conditions and traps that change answers; neither a list of formulas nor beyond the syllabus.
- examples: each worked example is a real GATE 2-mark-size problem that trains a distinct skill and shows the step students get wrong; none is a one-line substitution.
- figures: each figure shows something the student reads off it (a schedule, a peak, a path, a geometry), matches its example's numbers and is the right kind of diagram; no decorative or missing figures where GATE would draw one.
- questions: practice and sample questions are original, cover the archetypes, have distractors from real mistakes, and their solutions teach.

Return this JSON:
{"scores": {"correctness": 1-5, "gate_fidelity": 1-5, "depth": 1-5, "examples": 1-5, "figures": 1-5, "questions": 1-5},
 "worst": ["the three most important concrete weaknesses, each naming the section, example, figure or question"],
 "best": "one sentence on what is done well"}

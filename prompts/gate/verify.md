You are reviewing a GATE topic PDF on "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}) before it is published: first its answer key, then whether it actually teaches.

Below are its questions (with their stated answer and solution), its worked examples, and its figures (described by kind, caption and the labels and values they show). Solve each question and example yourself, independently, before you look at the stated answer.
{{ITEMS}}

Return this JSON:
{"issues": [{"ref": "<ref of the item>", "problem": "what is wrong, in one or two sentences", "correct": "the correct answer (letter(s) or number), or empty"}],
 "weak": [{"ref": "<ref of the item>", "problem": "what to change, concretely, in one or two sentences"}]}

"issues": items that are really wrong.
- the stated answer or a number in the working is wrong;
- an MCQ has no correct option or more than one; an MSQ key misses a correct option or includes a wrong one;
- the question is ambiguous or misses data, so that a careful student could defend a different answer (say what is missing);
- a worked example's result or an intermediate value is wrong.

"weak": items that are correct but do not teach, at most 6, the most important first.
- a worked example that is a one-line substitution into a formula, or tests the same skill as another example;
- a figure that does not show what its caption or section is about, whose numbers do not match the example it belongs to, or that is decorative (repeats a formula, meaningless labels, a diagram type that does not fit the idea);
- a question below GATE level (pure recall), or MCQ distractors that no real mistake would lead to.
Do not report wording, style or length. Return empty lists when everything is right.

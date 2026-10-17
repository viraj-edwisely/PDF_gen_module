# GATE-level standard

Every PDF is preparation for **GATE**, not for a university semester exam, a school board or a
placement test. The app checks the mechanical parts (question format, marks, answer checks); the
judgement parts are yours.

## Contents
1. The exam the content is calibrated to
2. Notes: what GATE-level depth means
3. Questions: types, phrasing, difficulty
4. Answer key conventions
5. Originality (non-plagiarised questions)
6. Self-review checklist

## 1. The exam the content is calibrated to
Confirm details against the official information brochure of the target year (the organising IIT
publishes it); the stable pattern for engineering papers is:

| Item | GATE pattern |
|---|---|
| Paper | 65 questions, 100 marks, 3 hours, computer-based, on-screen virtual scientific calculator |
| Sections | General Aptitude 15 marks (10 Q: 5 × 1 + 5 × 2) for every paper; Engineering Mathematics about 13 marks in most engineering papers; the rest is the core subject |
| Question types | **MCQ** (one correct of four), **MSQ** (one or more of four correct), **NAT** (numerical answer typed in, no options) |
| Marks | 1-mark and 2-mark questions only |
| Negative marking | MCQ only: −1/3 for a wrong 1-mark, −2/3 for a wrong 2-mark answer. MSQ and NAT: none |
| MSQ scoring | All correct options and no wrong option, else zero; no partial credit |
| NAT keys | A value or an accepted range (e.g. 7.19 to 7.21); stems state units and rounding |
| Pace | About 1.8 minutes per mark (180 min / 100 marks) |

Consequences for the content:
- No descriptive work: nothing asks the student to explain, derive, define, prove or "write a note".
  Derivations appear in notes only when the result is a formula GATE uses.
- Calculator arithmetic is fine; long hand computation that only tests stamina is not GATE-like.
- Units, sign conventions and code references follow what GATE papers use (SI units; Indian codes
  where the syllabus names them, e.g. IS 456:2000, IS 800:2007, IRC:37 for CE; standard textbook
  conventions otherwise, stated explicitly when GATE papers have used more than one).

## 2. Notes: what GATE-level depth means
Start from the topic's previous-year questions (those given in the task, and those you know GATE
has asked). List the **question archetypes** GATE has used for this topic (e.g. "SRTF average TAT with arrivals", "max BM under a
partial UDL", "eigenvalues of a triangular matrix"). The notes must equip the student for every
archetype, plus the obvious neighbours GATE has not yet asked.

Per GATE-testable idea, one numbered section with:
1. **Rule / definition** in one or two sentences, then when it applies (pre-emptive or not, valid only for a
   linear elastic material...), written as plain sentences without labels such as "Type:".
2. **The formula or method as GATE uses it**, with symbols defined and units.
3. **Why it works / when it fails**, only as far as it changes an answer (optimality, limiting cases,
   assumptions GATE questions quietly rely on).
4. **One worked example in GATE style** (a 2-mark-size problem, numbers that a calculator handles in
   2-4 minutes), solved step by step with the intermediate table/figure a topper would draw.
5. **A trap box** where GATE has set a trap before (sign/convention, tie-breaking, units, idle time,
   boundary cases).

Topic-level additions: "What you will learn" (3-5 verb-first outcomes), prerequisites by name, a
**comparison section** when the topic has several methods ("one problem, every method"), a **Common
GATE traps** list (5-10), and a **revision card** (5-8 lines, formulas and decision rules).

Depth guardrails:
- Too shallow (reject): a list of definitions and formulas with one example for the whole topic;
  examples that are plug-in with one step; no figures for a visual/numerical topic.
- Too deep (cut): research-level proofs, topics outside the official syllabus line, exotic variants
  never asked in GATE (if a variant is genuinely examinable, keep it to a short paragraph).
- Typical size: 4-12 sections, one worked example per section, a figure in most sections, 10-18 pages per topic.
  Small topics (e.g. a single aptitude idea) can be shorter but still need ≥ 3 worked examples.

## 3. Questions: types, phrasing, difficulty

### Difficulty calibration (all levels stay inside GATE)
| Level | GATE equivalent | What it looks like | Target time |
|---|---|---|---|
| Easy | 1-mark | One concept, direct application or a property question | ~1.5 min |
| Medium | 1- or 2-mark | Two steps, or one concept with a twist (arrivals, a non-standard support, a tie) | 2-3 min |
| Hard | 2-mark | Multi-step, combines two ideas, or a trap that catches a rushed method | 3-4 min |

"Hard" never means beyond GATE: no question should need more than ~4 minutes or knowledge outside
the syllabus line. Before writing practice, re-read 3-4 PYQs of the topic to anchor the level.

### Mix per topic
- Practice: 10-12 questions, Easy → Medium → Hard; about 30-50% NAT for numerical topics (fewer
  for theory-heavy topics), at least one MSQ, at least a third 2-mark.
- Sample paper: 5 questions / 8 marks / 12 minutes per topic (module-level paper: 15 Q / 25 marks /
  45 min), GATE-like mix, distinct from practice.
- Every original question records the PYQ archetype it mirrors in an internal `mirrors` field
  (never printed). If you cannot name one, ask whether GATE would really ask it.

### GATE phrasing
- MCQ: "Which one of the following is CORRECT?", "... is", "The value of ... is"; four concrete options.
  Distractors come from **real mistakes** (wrong convention, missed idle time, forgot a factor of 2,
  used the non-pre-emptive rule), each one a value or statement a student could actually reach.
  Avoid "all/none of the above".
- MSQ: "Which of the following statements is/are CORRECT?" / "... is/are TRUE?"; 1-4 correct;
  each option tests a separate idea.
- NAT: ends with "______", gives units in the stem, and states rounding when the answer is not an
  integer: "The average waiting time (in ms) is ______ (rounded off to two decimal places)."
- Data in the stem, not in prose puzzles; tables or figures for 4+ data items, as GATE does.
- Figures: when GATE would show a diagram (beam, circuit, graph, automaton, network, plot), the
  question has a `figure` and the stem says "shown in the figure".

## 4. Answer key conventions
- MCQ/MSQ: letters ("B", "A, C"). NAT: the value plus `answer_range` (exact for integers; otherwise wide enough
  to accept the usual approximations, such as 9550 for 60000/2π or π = 3.14, and the rounding of intermediate values).
- Every solution shows the working a student should write in 2-4 lines, with the key figure or
  table (`solution_figure`) when it is the fastest route, and for MCQ says why the tempting
  distractor is wrong when that is the point of the question.
- Solve every numeric answer step by step and give its "check" expression (see the schema): the app
  recomputes it. PYQ answers are the official key and are never changed; your solution must reach
  the official answer.

## 5. Originality (non-plagiarised questions)
- Practice, sample-paper questions and worked examples are written from scratch: new scenario, new
  data and, where possible, a different ask from any PYQ or published book question. Changing only the
  numbers of a PYQ or a coaching-book question is not original.
- Do not copy notes, examples or questions from textbooks, coaching material or websites. Standard
  results (formulas, named theorems) are common knowledge and fine.
- PYQs are reproduced verbatim only in the "Previous-year GATE questions" section, tagged with their
  source; they never appear as practice and practice never wears a GATE tag.

## 6. Self-review checklist (before you reply)
- [ ] Every PYQ archetype for the topic is covered by a worked example or a practice question.
- [ ] Each section: rule, method/formula, GATE-style worked example; traps where GATE sets them.
- [ ] Figures wherever GATE would draw one (see FIGURES), at least one in every section the plan asks for.
- [ ] Questions are objective, GATE-phrased, within 1.5-4 minutes, mix of MCQ/MSQ/NAT and 1/2 marks.
- [ ] Every number solved step by step with its "check"; NAT stems state units and rounding; answer ranges set.

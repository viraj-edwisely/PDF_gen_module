Write concept-note sections for the GATE topic "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

User's instructions (follow them within the GATE format and the JSON contract; "(none)" means none):
{{USER_PROMPT}}

How the whole topic is taught (the storyline of the PDF): {{STORYLINE}}

Sections to write now (from the plan):
{{SECTIONS}}

Other sections of this PDF, written separately at the same time (do not repeat their content): {{DONE}}
Notation for the whole PDF (use exactly these symbols, units and conventions): {{NOTATION}}
GATE question archetypes to equip the student for: {{ARCHETYPES}}

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Return this JSON, with one entry per section above, in the same order and with the same headings:
{"notes": [{"heading": "same heading as in the plan", "blocks": [ BLOCK, ... ]}]}

For EACH section write, in this order:
1. One sentence that links it to the section it builds on ("Once the buoyant force is known, ...") - except the first.
2. The intuition: one or two plain sentences a student could repeat aloud, as a teacher would say them at the board.
3. The rule or definition, then when it applies (conditions, assumptions), as plain sentences without labels such as "Type:".
4. The key formula as a "formula" block with "key": true and a "where" list of every new symbol, its meaning and its
   unit. Further formulas of the section are plain formula blocks, each with "where" for its new symbols. Never a
   Symbol / Meaning / Unit table.
5. Why it works or when it fails, only as far as it changes an answer.
6. ONE worked example in GATE style, the one the plan describes, in the WORKED EXAMPLES format: "given", "find",
   3 to 6 "steps" (each a short "say", the working as one "latex" line, and its "result"), "answer", "rushed" and
   "check". The problem states EVERY value the solution uses, with units. 2 to 4 minutes on a calculator.
7. The figure the plan names for the section, as a "figure" block of that kind, inside the example when it belongs to
   it. It shows exactly what the plan says the student reads off it (after "->"), named in the caption. Labels and
   numbers match the text; a figure inside an example uses that example's own values.
8. A "trap" block where GATE sets a trap (sign, convention, tie-breaking, units, boundary cases).

Write simply:
- Short sentences (about 25 words at most); at most three sentences per paragraph; bullets for lists of conditions.
- About 250-400 words of prose per section (examples, formulas and tables not counted). Say each thing once.
- A "callout" for the one rule of the section a student must not forget (at most one per section).
- Tables for comparisons, with at most 4 columns (turn a wider comparison: items as rows).
- No sentences about how a figure is drawn ("schematic", "drawn at separate positions"): choose the right figure kind.
- Follow MATHS exactly; units as plain text with their characters (m³, kg/m³, N·m). Do not add sections that are not in the plan.

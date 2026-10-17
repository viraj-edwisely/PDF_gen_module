Write concept-note sections for the GATE topic "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

User's instructions (follow them within the GATE format and the JSON contract; "(none)" means none):
{{USER_PROMPT}}

Sections to write now (from the plan):
{{SECTIONS}}

Other sections of this PDF, written separately at the same time (do not repeat their content): {{DONE}}
GATE question archetypes to equip the student for: {{ARCHETYPES}}

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Return this JSON, with one entry per section above, in the same order and with the same headings:
{"notes": [{"heading": "same heading as in the plan", "blocks": [ BLOCK, ... ]}]}

For EACH section write, in this order:
1. The rule or definition in one or two sentences, then when it applies (conditions, assumptions). Write it as plain sentences, with no labels such as "Type:".
2. The formula or method as GATE uses it, with symbols and units (formula blocks, or a table).
3. Why it works or when it fails, only as far as it changes an answer.
4. ONE worked example in GATE style, the one the plan describes: an "example" block with "problem", "solution" and "check". It trains the archetype the plan names and shows the step a rushed student gets wrong. 2 to 4 minutes on a calculator, solved step by step with the intermediate values. The problem states EVERY value the solution uses (material constants such as G or E, lengths, limits such as an allowed twist, diameters), with units.
5. The figure the plan names for the section (field "figure"), as a "figure" block, inside the example when it belongs to it. It must show exactly what the plan says the student reads off it (after "->"); mark that point (a labelled point, annotation, highlighted path or cell) and say it in the caption. Use the exact spec format of its kind; labels and numbers must match the text (P1, q0, R1...): a figure inside an example uses that example's own values, never another example's.
6. A "trap" block where GATE sets a trap (sign, convention, tie-breaking, units, boundary cases).
Use tables for comparisons, keep paragraphs short, and follow MATHS exactly. Do not add sections that are not in the plan.

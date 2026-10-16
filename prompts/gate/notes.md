Write concept-note sections for the GATE topic "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

Sections to write now (from the plan):
{{SECTIONS}}

Other sections of this PDF, written separately at the same time (do not repeat their content): {{DONE}}
GATE question archetypes to equip the student for: {{ARCHETYPES}}

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Return this JSON:
{"notes": [{"heading": "same heading as in the plan", "blocks": [ ...blocks as defined in the schema... ]}]}

For EACH section write, in this order:
1. The rule or definition in one or two sentences, then its type or condition.
2. The formula or method as GATE uses it, with symbols and units (a formula block, or a table).
3. Why it works or when it fails, only as far as it changes an answer.
4. ONE worked example in GATE style (block type "example", with problem and solution), 2 to 4 minutes on a calculator, solved step by step. Add a figure block inside it whenever a topper would sketch one (see the figure catalogue). Verify the numbers.
5. A "trap" block where GATE sets a trap (sign, convention, tie-breaking, units, boundary cases).
Use tables for comparisons, and keep paragraphs short. Do not add sections that are not in the plan.

Write these topics of the module "{{MODULE}}" ({{SUBJECT}}).

Topics to write now (title, tagline, focus):
{{TOPICS}}

Other topics of the module, written separately at the same time (do not repeat their content): {{OTHERS}}

User's instructions (empty means use the standard template):
{{USER_PROMPT}}

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Return this JSON: {"topics": [{"blocks": [ BLOCK, ... ]}]}  with one entry per topic above, in the same order.
For each topic follow the standard topic template (situation, table or concept, worked_example, pitfall, quick_check with 2 questions) unless the user's instructions say otherwise. Make each worked example numeric and verify the numbers.

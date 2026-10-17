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
For each topic follow the standard topic template (situation, table or concept, worked_example, pitfall, quick_check with 2 questions) unless the user's instructions say otherwise.
Make each worked example numeric where the subject allows, solve it step by step and give its "check". Add a "figure" block where a chart, timeline or diagram makes the idea clearer, with the exact spec of its kind: it uses the numbers of the text next to it and shows something the student reads off it (a peak, a crossing, a trend), named in its caption; no decorative figures. Each worked example is a realistic multi-step problem, not a one-line substitution into a formula. Follow MATHS exactly.

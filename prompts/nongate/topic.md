Write topic {{N}} of the module "{{MODULE}}" ({{SUBJECT}}).

Topic: {{TITLE}}
Tagline: {{TAGLINE}}
Focus: {{FOCUS}}

User's instructions (empty means use the standard template):
{{USER_PROMPT}}

Titles of the other topics (do not repeat their content): {{OTHERS}}

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Return this JSON: {"blocks": [ BLOCK, ... ]}
Follow the standard topic template (situation, table or concept, worked_example, pitfall, quick_check with 2 questions) unless the user's instructions say otherwise. Make the worked example numeric and verify the numbers.

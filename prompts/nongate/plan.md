Plan a learning module with these topics: {{TOPICS}}
Subject: {{SUBJECT}}

User's instructions (they override the standard template where they conflict; empty means use the standard template):
{{USER_PROMPT}}

{{BOOK_NOTE}}
<book>
{{BOOK}}
</book>

Return this JSON:
{
  "title": "module title", "description": "2-3 sentences, under 350 characters",
  "study_time": "{{STUDY_TIME}}", "audience": "{{AUDIENCE}}",
  "topics": [{"title": "...", "tagline": "one line", "focus": "what this topic covers and the worked-example idea"}],
  "case_study": true or false, "n_practice": 10 to 12
}
If study_time or audience above are empty, choose sensible values. Keep the topics in the order given unless the user's instructions say otherwise; you may add topics only if the user asks.

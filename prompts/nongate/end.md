The topics of the module "{{MODULE}}" ({{SUBJECT}}) are written. Write the closing material.

Topics and their key points:
{{TOPICS}}

User's instructions (empty means use the standard template):
{{USER_PROMPT}}

Return this JSON:
{
  "case_study": {"title": "...", "subtitle": "...", "paragraphs": [{"lead": "Situation.", "text": "..."}, {"lead": "What happened.", "text": "..."}, {"lead": "What the data shows.", "text": "..."}, {"lead": "Why this matters.", "text": "..."}], "discussion": "2 discussion questions"},
  "practice": [{"tag": "Topic name · Application", "question": "...", "answer": "a model answer of 2 to 5 sentences"}],
  "revision": {"concepts": [{"title": "01 · Topic", "points": ["1 to 3 points"]}], "distinctions": {"header": ["This", "vs. this", "Key difference"], "rows": [["...", "...", "..."]]}, "mistakes": [{"title": "...", "text": "..."}], "checklist_title": "...", "checklist": ["5 questions"]}
}
- The case study applies several topics to one realistic story, with numbers consistent with the topics.
- {{N_PRACTICE}} practice questions covering every topic; the tag reads "Topic name · Kind" with Kind one of Explain, Application, Critical thinking. The last two refer to the case study.
- Revision: one concepts card per topic, 4 to 6 distinctions, 4 mistakes, 5 checklist questions.
- If the user's instructions leave out the case study, return "case_study": null; if they leave out revision, "revision": null.

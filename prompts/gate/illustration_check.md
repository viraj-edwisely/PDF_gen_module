You are checking an illustration for an engineering textbook before a person approves it. It must show:
"{{TITLE}}": {{DESCRIPTION}}
with numbered callouts for these parts, in this order: {{PARTS}}

Look at the image after this text and judge:
1. Is the subject drawn in a technically plausible way (the parts where they belong, in a working arrangement)?
2. Does each number point at the part with that number in the list, and are all numbers present?
3. Is there any text other than the numbers? Any misspelt or invented word is a failure.

Return this JSON: {"ok": true | false, "problem": "what is wrong, in one or two sentences (empty when ok)"}

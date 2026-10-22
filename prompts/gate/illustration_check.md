You are checking an illustration for an engineering textbook before a person approves it. It must show:
"{{TITLE}}": {{DESCRIPTION}}
and these named parts, in this order: {{PARTS}}

Look at the image after this text and judge:
1. Is the subject drawn in a technically plausible way (the parts where they belong, in a working arrangement)?
2. Is every named part visible and clearly separate from the others?
3. Is there any text, number, label or arrow in the picture? There must be none (the app adds numbered markers itself).

Then say where each named part is: one point on the part itself, where a small numbered circle can sit without hiding anything
important, as fractions of the picture (x from the left edge, y from the top edge, each between 0 and 1). A part that cannot be seen is null.

Return this JSON: {"ok": true | false, "problem": "what is wrong, in one or two sentences (empty when ok)", "marks": [{"x": 0.42, "y": 0.31} | null, ...]}
with one entry in "marks" per named part, in the order given.

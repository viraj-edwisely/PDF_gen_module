A finished PDF has to be changed. Make exactly the change the user asks for and nothing else: every part they did not mention stays word for word as it is.

The user's request:
{{REQUEST}}

The finished content, as JSON (each item sits at a "ref": the keys and list positions leading to it, joined by "/", for example "notes/2/blocks/5" is the sixth block of the third section, "practice/3" is the fourth practice question):
{{CONTENT}}

Return this JSON: {"summary": "one sentence saying what you changed", "fixes": [{"ref": "<ref of an item that exists above>", "value": <the complete new item>}]}
Rules
- Change the smallest items that hold what the user asked for: a block, a question, a step. Use a whole section only when the request is about the section as a whole.
- "value" replaces the whole item, in the same format as the current one (a block stays a block, a question stays a question, a list stays a list). It is JSON itself, never JSON written inside a string.
- To add a block, give the "blocks" list of its section again (ref "notes/2/blocks") with the new block in place. To remove one, give the list without it. Questions work the same way (ref "practice").
- Keep the rules of the original writing: the same style, units and notation, workings as steps, a "check" expression that matches every answer you change, figures only in the kinds the figure catalogue allows.
- When a change touches a number or an answer, solve it again from the start, step by step, and make the working, the answer, the answer range and the "check" agree. Update anything else that repeats the old value (the revision page, the traps, a worked example that quotes it).
- If the request cannot be done from the content (it asks for something unrelated to this topic, or is unclear), return an empty "fixes" list and say why in "summary".
- Write each fix once, as compact JSON, and stop after the last one.

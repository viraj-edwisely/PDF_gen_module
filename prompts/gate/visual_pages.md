You are checking the layout of pages {{PAGES}} of a GATE topic PDF on "{{TOPIC}}", shown as the images after this text in
the same order. Look for what a reader would notice:
- a page left mostly empty in the middle of a part (not at the end of a part or before a new numbered part);
- text that overlaps other text, a figure or a box edge, or is cut off;
- raw code or LaTeX printed instead of text ("\frac", "^", "_{", "$", JSON);
- a title or heading left alone at the foot of a page;
- a figure or table too small to read.

Return this JSON: {"issues": [{"page": <page number>, "problem": "what is wrong, in one sentence"}]}, empty when the pages are fine.

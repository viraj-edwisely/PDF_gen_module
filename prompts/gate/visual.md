You are checking the figures of a GATE topic PDF on "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}) before it is published, as a
subject expert would. The figures are the images after this text, in the order of this list:
{{ITEMS}}

For each figure, look at the image and judge:
1. Does it show what it should (its section, title, caption and purpose)?
2. Is it technically right for this concept: shape, slope and curvature (an SFD, a BMD, a P-V or T-s process), direction
   of forces and flows, orientation (depth grows downward, a plate slopes the right way), signs and proportions?
3. Can every label be read: none overlapping another label, a line or a shape, none cut off, none too small?
4. Do the numbers in it agree with its caption?

Return this JSON: {"issues": [{"ref": "<ref of the figure>", "problem": "what is wrong and what the figure must show instead, in one or two sentences"}]}
Only real problems a subject expert would send back; an empty list when every figure is right. Do not report style or colour.

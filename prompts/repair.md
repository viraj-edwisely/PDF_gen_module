The automatic checks found problems in some items of the JSON you wrote. Fix only these items.

Each item has a "ref" (where it sits in the JSON), the "problems" found, and its "current" JSON (null if it is missing):
{{ITEMS}}

Return this JSON: {"fixes": [{"ref": "<the same ref>", "value": <the complete corrected item>}]}, one entry per item above.
Rules
- "value" replaces the whole item, in the same format as the current one (a block stays a block of the same kind, a question stays a question, a list stays a list).
- Fix every problem listed for the item and keep everything else as it was.
- When a problem is about a number or an answer, solve the problem again from the start, step by step, and make the working, the answer, the answer range and the "check" expression agree.
- When an item is missing (current is null), write it.

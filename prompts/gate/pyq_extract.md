Below is a source (a web page, or the text of a PDF or Word file) that may contain previous-year GATE questions. Find the questions that test this topic: "{{TOPIC}}" ({{PAPER}} · {{SUBJECT}}).

<source>
{{SOURCE}}
</source>

Return this JSON: {"questions": [ {"source": "{{PAPER}}-GATE-<year>", "qtype": "MCQ|MSQ|NAT", "marks": 1 or 2, "question": "...", "options": ["...", "...", "...", "..."], "answer": "B", "answer_range": "only for NAT", "solution": "2 to 4 lines of working that reach the official answer"} ]}

Rules
- Copy "question" and the options VERBATIM from the source (fix only obvious extraction damage). Do not paraphrase, shorten or complete a question.
- "answer" must be the official answer stated in the source. If the source does not state the answer, leave "answer" null. Never work out or change an official answer yourself.
- "source" needs the paper code and the year as shown in the source (for example CS-GATE-2019). If the year is not shown, leave "source" null.
- Include only questions that really test this topic. Return {"questions": []} if there are none.
- NAT questions have no options; MCQ and MSQ have exactly four.

#!/usr/bin/env python3
"""Check a topic content JSON against the GATE-level standard (references/gate_level_standard.md).

Usage: python3 check_gate_level.py work/content/<TOPICID>.json [more.json ...]
Exit code 1 if any ERROR. WARNINGs are judgement calls: read them and fix or consciously accept.
Run it on every topic JSON before rendering; build_all.py runs it too.
"""
import json, re, sys

NON_GATE_STEMS = re.compile(r'^\s*(explain|describe|derive|define|discuss|write (a )?(short )?note|what (do you mean|is meant)|'
                            r'list (the|all)|state and prove|prove that|elaborate|differentiate between|compare and contrast)\b', re.I)
ROUND = re.compile(r'round(ed)? off|decimal place|integer|nearest|significant', re.I)
LEVELS = ['Easy', 'Medium', 'Hard']
ID_LEAK = re.compile(r'\b[A-Z]{2,5}-U\d\d-T\d\d\b|\b[A-Z]{2,4}-S\d+-T\d+\b|\bG[A-Z]{1,3}-M\d\d\b|GATE\s*20\d\d(?!\d)')


def walk_text(x):
    if isinstance(x, str): yield x
    elif isinstance(x, list):
        for y in x: yield from walk_text(y)
    elif isinstance(x, dict):
        for k, v in x.items():
            if k in ('source', 'topic_id', 'module_id', 'module_name', 'exam', 'path', 'kind', 'spec', 'mirrors'): continue
            yield from walk_text(v)


def walk_blocks(bs):
    for b in bs or []:
        if isinstance(b, dict):
            yield b
            for k in ('problem', 'solution', 'blocks'):
                if isinstance(b.get(k), list): yield from walk_blocks(b[k])


def check(path):
    c = path if isinstance(path, dict) else json.load(open(path)); E, W = [], []
    paper = c.get('paper', '').upper()

    # ---------------- notes depth
    notes = c.get('notes', [])
    if len(notes) < 3: E.append(f'only {len(notes)} concept sections - split the syllabus line into its GATE-testable ideas (usually 4-12)')
    n_ex = 0
    for i, s in enumerate(notes, 1):
        bl = list(walk_blocks(s.get('blocks', [])))
        ex = [b for b in bl if b.get('type') == 'example']; n_ex += len(ex)
        if not ex and not s.get('no_example'):
            W.append(f'notes {i} "{s["heading"]}" has no worked example (add one, or set "no_example": true for a pure-definition section)')
    if n_ex < max(3, len(notes) - 2): E.append(f'{n_ex} worked examples for {len(notes)} sections - GATE prep needs one solved GATE-style problem per idea')
    figs = sum(1 for s in notes for b in walk_blocks(s.get('blocks', [])) if b.get('type') in ('figure', 'image'))
    if figs == 0: W.append('no figures - most GATE topics need at least one diagram/graph/plot (see figure_catalogue.md)')
    if not c.get('traps'): E.append('missing "traps": list the 5-10 mistakes GATE questions are designed to catch')
    if not (5 <= len(c.get('revision_card', [])) <= 10): W.append('revision card should have 5-8 one-liners')

    # ---------------- questions
    def qcheck(q, where, original):
        t = q.get('qtype', '').upper(); stem = q.get('question', '')
        if t not in ('MCQ', 'MSQ', 'NAT'): E.append(f'{where}: qtype must be MCQ/MSQ/NAT (GATE has no other types)')
        if q.get('marks') not in (1, 2): E.append(f'{where}: marks must be 1 or 2')
        if not q.get('answer'): E.append(f'{where}: no answer')
        if not q.get('solution'): E.append(f'{where}: no worked solution')
        if original and NON_GATE_STEMS.search(stem): E.append(f'{where}: descriptive/university-style stem ("{stem[:40]}...") - GATE asks only objective MCQ/MSQ/NAT')
        if t in ('MCQ', 'MSQ'):
            if len(q.get('options') or []) != 4: E.append(f'{where}: {t} needs exactly 4 options')
            letters = [x.strip() for x in str(q.get('answer', '')).split(',') if x.strip()]
            if any(x not in 'ABCD' or len(x) != 1 for x in letters): E.append(f'{where}: answer must be option letters, e.g. "B" or "A, C"')
            if t == 'MCQ' and len(letters) != 1: E.append(f'{where}: MCQ has exactly one correct option')
            if original and t == 'MCQ' and len(set(map(str, q.get('options') or []))) < 4: E.append(f'{where}: duplicate options')
            if original and any(re.search(r'all of the above|none of the above|both \(?a\)? and', str(o), re.I) for o in q.get('options') or []):
                W.append(f'{where}: "all/none of the above" options are rare in GATE - prefer four concrete options (MSQ if several are true)')
            if original and t == 'MSQ' and 'is/are' not in stem.lower() and 'are true' not in stem.lower() and 'correct' not in stem.lower():
                W.append(f'{where}: MSQ stems in GATE say "Which of the following is/are CORRECT?"')
        if t == 'NAT':
            if q.get('options'): E.append(f'{where}: NAT must not have options')
            if original:
                try:
                    v = float(str(q.get('answer')).split()[0])
                    if v != int(v) and not ROUND.search(stem): E.append(f'{where}: non-integer NAT answer but the stem gives no rounding instruction ("rounded off to two decimal places")')
                except (ValueError, IndexError, OverflowError): E.append(f'{where}: NAT answer must be a number (ranges go in "answer_range")')
                if not q.get('answer_range'): W.append(f'{where}: add "answer_range" (GATE keys accept a range, e.g. "7.19 to 7.21")')
                if '___' not in stem: W.append(f'{where}: NAT stems end with a blank "______" and the unit/rounding')
        if original and q.get('source'): E.append(f'{where}: original questions must not carry a GATE source tag')
        if original and len(stem) < 25: W.append(f'{where}: stem very short - is it really a GATE-level question?')

    for i, q in enumerate(c.get('pyqs', []), 1):
        if not re.fullmatch(rf'{paper}-GATE-(19|20)\d\d', str(q.get('source', ''))): E.append(f'PYQ{i}: source must be like {paper}-GATE-2019')
        qcheck(q, f'PYQ{i}', False)
    pr = c.get('practice', [])
    for i, q in enumerate(pr, 1):
        qcheck(q, f'P{i}', True)
        if q.get('level') not in LEVELS: E.append(f'P{i}: level must be Easy/Medium/Hard')
        if q.get('level') == 'Hard' and q.get('marks') != 2: W.append(f'P{i}: Hard questions should be GATE 2-mark questions')
        if q.get('level') == 'Easy' and q.get('marks') != 1: W.append(f'P{i}: Easy questions should be GATE 1-mark questions')
    if pr:
        if len(pr) < 8: W.append(f'{len(pr)} practice questions - aim for 10-12')
        order = [LEVELS.index(q['level']) for q in pr if q.get('level') in LEVELS]
        if order != sorted(order): E.append('practice must run Easy -> Medium -> Hard')
        types = {t: sum(q.get('qtype') == t for q in pr) for t in ('MCQ', 'MSQ', 'NAT')}
        if types['NAT'] < max(2, len(pr) // 4): W.append(f'only {types["NAT"]} NAT - numerical topics in GATE are NAT-heavy (aim 30-50%)')
        if types['MSQ'] == 0: W.append('no MSQ - include at least one')
        if sum(q.get('marks') == 2 for q in pr) < len(pr) // 3: W.append('too few 2-mark questions - at least a third should be multi-step 2-mark problems')
    sp = c.get('sample_paper') or {}
    qs = sp.get('questions', [])
    for i, q in enumerate(qs, 1): qcheck(q, f'S{i}', True)
    if qs:
        tot = sum(q.get('marks', 0) for q in qs)
        if sp.get('marks') != tot: E.append(f'sample paper says {sp.get("marks")} marks but questions add to {tot}')
        m = re.search(r'\d+', str(sp.get('duration', '')))
        if m and not (1.2 * tot <= int(m.group()) <= 2.2 * tot): W.append(f'sample paper time {m.group()} min for {tot} marks - GATE pace is about 1.8 min per mark')
        stems = {q['question'] for q in pr}
        if any(q['question'] in stems for q in qs): E.append('sample paper repeats a practice question')

    # ---------------- leaks
    for t in walk_text({k: v for k, v in c.items()}):
        m = ID_LEAK.search(t)
        if m: E.append(f'internal ID or target exam year printed in the PDF text: "{m.group()}"'); break
    return E, W


if __name__ == '__main__':
    bad = 0
    for p in sys.argv[1:]:
        E, W = check(p)
        print(f'== {p}: {len(E)} error(s), {len(W)} warning(s)')
        for e in E: print('  ERROR  ', e)
        for w in W: print('  warning', w)
        bad += bool(E)
    sys.exit(1 if bad else 0)

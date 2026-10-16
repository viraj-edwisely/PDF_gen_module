#!/usr/bin/env python3
"""GATE topic PDF: locked Edwisely frame (cover, contents, header, footer, watermark) + body from content JSON.

Usage: python render_gate.py content.json out.pdf      (schema: prompts/gate/content_schema.md)
"""
import json, sys
from render_common import *

def fig_width(f):
    if not isinstance(f, dict): return None
    return f.get('width') or (1.0 if f.get('kind') in ('gantt', 'timeline') else None)


def q_figure(q, key):
    if q.get(key + '_figure'): return figure_path(q[key + '_figure'])
    return q.get(key + '_image') if key != 'question' else (q.get('image') or (figure_path(q['figure']) if q.get('figure') else None))


def question(q, n, show_tag=True):
    head = []
    if show_tag:
        bits = [q.get('source'), q.get('level'), q.get('qtype'), f"{q['marks']} mark{'s' if q.get('marks', 1) != 1 else ''}" if q.get('marks') else None]
        head.append(tag(' · '.join(b for b in bits if b)))
    body = [Paragraph(f'<font name="Head" color="#4D2A87">Q{n}.</font> ' + rich(q['question']), S['body'])]
    qi = q_figure(q, 'question')
    if qi and os.path.exists(qi): body.append(image(qi, maxh=95 * mm, width=fig_width(q.get('figure'))))
    if q.get('options'):
        opts = [Paragraph(f'<font name="HeadM">({"ABCD"[k]})</font> ' + rich(o), S['cell']) for k, o in enumerate(q['options'])]
        short = all(len(o) < 38 for o in q['options'])
        rows = [opts[0:2], opts[2:4]] if short and len(opts) == 4 else [[o] for o in opts]
        t = Table(rows, colWidths=[(W - 2 * M - 14) / len(rows[0])] * len(rows[0])); t.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 14), ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        body.append(t)
    elif q.get('qtype', '').upper() == 'NAT':
        body.append(P('Answer: ________ (numerical value)', 'small'))
    return KeepTogether(head + body + [Spacer(1, 8)])


def answer_line(q, label):
    ans = q.get('answer', '')
    sol = q.get('solution', '')
    if q.get('answer_range') and str(q['answer_range']) != f'{ans} to {ans}':
        ans = f"{ans} (accepted range {q['answer_range']})"
    return [Paragraph(f'<font name="Head" color="#4D2A87">{label}</font>  <b>Answer: {html.escape(str(ans))}</b>'
                      + (f'  <font color="#6B6480">({html.escape(q["source"])})</font>' if q.get('source') else ''), S['body'])] + \
           ([P(x) for x in sol.split('\n\n')] if isinstance(sol, str) and sol else blocks(sol) if sol else []) + \
           ([image(q_figure(q, 'solution'), width=fig_width(q.get('solution_figure')))] if q_figure(q, 'solution') else []) + [Spacer(1, 4)]




def main():
    c = json.load(open(sys.argv[1], encoding='utf-8')); out = sys.argv[2]
    paper = c.get('paper', '').upper()
    footer_txt = f"GATE Readiness Programme · {paper} · {c.get('subject', '')}"
    logo_w = LOGO_WHITE

    def first(cv, doc):
        cv.saveState()
        cv.setFillColor(PURPLE); cv.rect(0, H - band, W, band, stroke=0, fill=1)
        lw = 34 * mm; cv.drawImage(logo_w, M, H - 19 * mm, lw, lw * 262 / 644, mask='auto')
        cv.setFillColor(YEL); cv.rect(M, H - band + 5 * mm, 26 * mm, 2.2 * mm, stroke=0, fill=1)
        cv.setFont('Body', 7.5); cv.setFillColor(GREY); cv.drawString(M, 10 * mm, 'Edwisely · ' + footer_txt)
        cv.drawRightString(W - M, 10 * mm, f'Page {doc.page}'); cv.restoreState()

    def later(cv, doc):
        cv.saveState()
        cv.setFillColor(PURPLE); cv.rect(0, H - 9 * mm, W, 9 * mm, stroke=0, fill=1)
        cv.setFillColor(colors.white); cv.setFont('HeadM', 8.5)
        cv.drawString(M, H - 6 * mm, f"{paper} · {c.get('subject', '')}")
        cv.setFont('HeadR', 8); cv.drawRightString(W - M, H - 6 * mm, c['topic_name'])
        cv.setStrokeColor(LINE); cv.line(M, 14 * mm, W - M, 14 * mm)
        cv.setFont('Body', 7.5); cv.setFillColor(GREY); cv.drawString(M, 10 * mm, footer_txt)
        cv.drawRightString(W - M, 10 * mm, f'Page {doc.page}')
        if c.get('contents', True):                       # clickable link back to the contents page
            cv.setFont('HeadM', 7.5); cv.setFillColor(PURPLE); lab = 'Back to contents'
            tw = cv.stringWidth(lab, 'HeadM', 7.5); x0 = W / 2 - tw / 2
            cv.drawString(x0, 10 * mm, lab); cv.linkRect('', 'contents', (x0 - 2, 8.5 * mm, x0 + tw + 2, 13 * mm), relative=0, thickness=0)
        cv.restoreState()

    doc = TopicDoc(out, pagesize=A4, title=f"{c['topic_name']} - {paper} GATE", author='Edwisely',
                          leftMargin=M, rightMargin=M, topMargin=16 * mm, bottomMargin=18 * mm)
    fr1 = Frame(M, 18 * mm, W - 2 * M, H - 18 * mm - 20 * mm, id='f1')
    fr2 = Frame(M, 18 * mm, W - 2 * M, H - 18 * mm - 16 * mm, id='f2')
    wm_end = watermark
    doc.addPageTemplates([PageTemplate('first', [fr1], onPage=first, onPageEnd=wm_end),
                          PageTemplate('later', [fr2], onPage=later, onPageEnd=wm_end)])

    story = [NextPageTemplate('later')]
    kick = f"{paper} · {c.get('subject', '').upper()}"
    head = [Paragraph(html.escape(kick), S['kicker']), Spacer(1, 6), Paragraph(rich(c['topic_name'], color='#FFFFFF'), S['title']),
            Spacer(1, 6), Paragraph(rich(c.get('subtitle', 'Topic guide: concept notes, worked examples, previous-year GATE questions, practice and sample paper'), color='#FFFFFF'), S['sub'])]
    head_h = max(60 * mm, sum(p.wrap(W - 2 * M, 0)[1] for p in head if isinstance(p, Paragraph)) + 6 + 4 + 6)     # a long title or subtitle makes the purple band taller
    band = 20 * mm + head_h + 4 * mm
    ht = Table([[head]], colWidths=[W - 2 * M], rowHeights=[head_h])
    ht.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 4)]))
    story += [ht, Spacer(1, 10 * mm)]
    def walk(bs):
        for b in bs:
            if not isinstance(b, dict): continue
            yield b
            for k in ('problem', 'solution', 'blocks'):
                if isinstance(b.get(k), list): yield from walk(b[k])
    allb = [b for s_ in c.get('notes', []) for b in walk(s_.get('blocks', []))]
    n_ex = sum(b.get('type') == 'example' for b in allb); n_fig = sum(b.get('type') in ('figure', 'image') for b in allb)
    parts = [f"Concept notes on {len(c.get('notes', []))} ideas" + (f" with {n_ex} worked examples" if n_ex else '') +
             (f" and {n_fig} figures" if n_fig else '')]
    if c.get('traps'): parts.append('common GATE traps')
    parts += ([f"{len(c['pyqs'])} previous-year questions"] if c.get('pyqs') else []) + [f"{len(c.get('practice', []))} practice questions",
              f"sample paper ({len(c.get('sample_paper', {}).get('questions', []))} Q)"]
    meta = [['Subject', c.get('subject', '')], ['Syllabus line', c.get('syllabus_line', '')], ['In this PDF', ' · '.join(parts)]]
    mt = Table([[Paragraph(f'<font name="HeadM">{k}</font>', S['cell']), Paragraph(rich(v), S['cell'])] for k, v in meta],
               colWidths=[34 * mm, W - 2 * M - 34 * mm])
    mt.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, LINE), ('BACKGROUND', (0, 0), (0, -1), LAV),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story += [mt, Spacer(1, 8)]
    sec = 0
    def h1(t):
        nonlocal sec; sec += 1
        return [CondPageBreak(40 * mm), mark(Paragraph(f'{sec}. {html.escape(t)}', S['h1']), 0, f'{sec}. {t}')]
    if c.get('objectives'):
        story += h1('What you will learn') + blocks([{'type': 'bullets', 'items': c['objectives']}])
    if c.get('prerequisites'):
        story += [box([P('**Before you start:** ' + '; '.join(c['prerequisites']))]), Spacer(1, 6)]
    if c.get('contents', True):
        story += [PageBreak()] + contents_block() + [PageBreak()]
    story += h1('Concept notes')
    notes_no = sec
    for j, s_ in enumerate(c.get('notes', []), 1):
        num = f'{notes_no}.{j} ' if c.get('number_notes', True) else ''
        story += [CondPageBreak(32 * mm), mark(Paragraph(num + rich(s_['heading']), S['h2']), 1, num + s_['heading'])] + blocks(s_.get('blocks', []))
    if c.get('traps'):
        story += h1('Common GATE traps') + blocks([{'type': 'bullets', 'items': c['traps']}])
    if c.get('revision_card'):
        story += h1('Revision card') + [box([Paragraph('<font name="Head" color="#FFE100">Key points to remember</font>', S['callout'])] +
                                             [Paragraph('• ' + rich(x, color='#FFFFFF'), S['callout']) for x in c['revision_card']], bg=PURPLE, bar=YEL)]
    if c.get('pyqs'):
        story += h1('Previous-year GATE questions') + [P(c.get('pyq_note', 'Official GATE questions on this topic, tagged by paper and year. '
                                                                     'Answers and solutions are at the end of this PDF.'), 'small')]
        for k, q in enumerate(c['pyqs'], 1): story.append(question(q, k))
    if c.get('practice'):
        story += h1('Practice questions') + [P('Original GATE-level questions, graded easy → hard (Easy ≈ GATE 1-mark, Hard ≈ GATE 2-mark). '
                                               'Clear 70% before moving on; answers and solutions at the end.', 'small')]
        for k, q in enumerate(c['practice'], 1): story.append(question(q, k))
    sp = c.get('sample_paper')
    if sp and sp.get('questions'):
        story += [PageBreak()] + h1(sp.get('title', 'Sample paper'))
        story += [styled_table(['Questions', 'Marks', 'Time', 'Marking'],
                               [[len(sp['questions']), sp.get('marks', ''), sp.get('duration', ''),
                                 sp.get('marking', 'GATE marking: wrong MCQ −1/3 (1-mark) or −2/3 (2-mark); no negative marking for MSQ and NAT; MSQ has no partial credit')]],
                               [24 * mm, 20 * mm, 22 * mm, W - 2 * M - 66 * mm]), Spacer(1, 8)]
        for k, q in enumerate(sp['questions'], 1): story.append(question(q, k))
    story += [PageBreak()] + h1('Answer key and solutions')
    for title, key, lab in (('Previous-year GATE questions', 'pyqs', 'PYQ'), ('Practice questions', 'practice', 'P'),
                            ('Sample paper', None, 'S')):
        qs = c.get(key, []) if key else (sp or {}).get('questions', [])
        if not qs: continue
        story.append(mark(Paragraph(title, S['h2']), 1, title))
        for k, q in enumerate(qs, 1): story += answer_line(q, f'{lab}{k}.')
    doc.multiBuild(story)   # two passes: the second fills in contents page numbers
    print('written', out)


if __name__ == '__main__':
    main()

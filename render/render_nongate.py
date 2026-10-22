#!/usr/bin/env python3
"""Non-GATE module PDF in the Edwisely "learning module" style: cover with tiles, contents, topic banners,
Situation / Concept / Worked example / Pitfall / Note boxes, Quick Checks, case study, practice, model answers
and a revision sheet.

Usage: python render_nongate.py content.json out.pdf      (schema: prompts/nongate/content_schema.md)
"""
import json, sys
from render_common import *

LABEL = ParagraphStyle('label', fontName='HeadM', fontSize=7.8, leading=10, textColor=PURPLE, spaceAfter=3)
KICK = ParagraphStyle('kick', fontName='HeadM', fontSize=8.5, leading=11, textColor=YEL)
BTITLE = ParagraphStyle('btitle', fontName='Head', fontSize=17, leading=22, textColor=colors.white)
BSUB = ParagraphStyle('bsub', fontName='HeadR', fontSize=9.5, leading=13, textColor=colors.HexColor('#D9D0EE'))
TILE = ParagraphStyle('tile', fontName='Head', fontSize=11.5, leading=15, textColor=PURPLE)
QS = ParagraphStyle('qs', fontName='BodyB', fontSize=9.6, leading=14, textColor=PURPLE, spaceAfter=2)
CREAM = colors.HexColor('#FFFBE0')
BOXES = {'situation': ('SITUATION', LAV, PURPLE), 'concept': ('CONCEPT', LAV, PURPLE), 'note': ('NOTE', LAV, PURPLE),
         'worked_example': ('WORKED EXAMPLE', CREAM, YEL), 'pitfall': ('COMMON PITFALL', CREAM, YEL)}


def labelled_box(kind, b):
    label, bg, bar = BOXES[kind]
    inner = [keep(Paragraph(html.escape(label + (' · ' + b['title'].upper() if b.get('title') else '')), LABEL))]
    inner += [P(x) for x in b['text'].split('\n\n')] if not blank(b.get('text')) else []
    if len(inner) == 1 and not b.get('blocks'): return []           # a label and nothing in the box
    return [box(inner + blocks(b.get('blocks', []), INNER), bg=bg, bar=bar), Spacer(1, 8)]


def quick_check(b, n):
    inner = [keep(Paragraph(f'QUICK CHECK · TOPIC {n:02d}', LABEL))]
    for qa in b.get('items') or []:
        if isinstance(qa, dict) and not blank(qa.get('q')): inner += [keep(Paragraph(rich('Q. ' + qa['q']), QS)), P('A. ' + qa.get('a', ''))]
    return [box(inner), Spacer(1, 8)] if len(inner) > 1 else []


def topic_body(items, n):
    out = []
    for b in items:
        t = b.get('type', 'para') if isinstance(b, dict) else 'para'
        if t in BOXES: out += safely(f'A "{t}" box', labelled_box, t, b)
        elif t == 'quick_check': out += safely('A quick check', quick_check, b, n)
        elif t == 'table' and b.get('title') and b.get('rows'): out += [CondPageBreak(40 * mm), Paragraph(html.escape(b['title'].upper()), LABEL)] + blocks([b])
        else: out += blocks([b])
    return out


def banner(kicker, title, tagline=None):
    cell = [Paragraph(html.escape(kicker), KICK), Paragraph(rich(title, color='#FFFFFF'), BTITLE)]
    if tagline: cell.append(Paragraph(rich(tagline, color='#D9D0EE'), BSUB))
    t = Table([[cell]], colWidths=[TW])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PURPLE), ('ROUNDEDCORNERS', [5, 5, 5, 5]),
                           ('LEFTPADDING', (0, 0), (-1, -1), 14), ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 12)]))
    return t


def section_head(kicker, title, intro=None):
    bar = Table([['']], colWidths=[11 * mm], rowHeights=[2 * mm]); bar.hAlign = 'LEFT'
    bar.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), YEL)]))
    return [PageBreak(), Paragraph(html.escape(kicker), LABEL), mark(Paragraph(rich(title), S['h1']), 0, title), bar, Spacer(1, 6)] + \
           ([P(intro, 'small'), Spacer(1, 6)] if intro else [])


def tiles(pairs):
    cells = [[Paragraph(html.escape(k.upper()), LABEL), Paragraph(rich(v), TILE)] for k, v in pairs]
    t = Table([cells[i:i + 2] for i in range(0, len(cells), 2)], colWidths=[TW / 2] * 2)
    t.setStyle(TableStyle([('LINEBEFORE', (0, 0), (-1, -1), 2.5, PURPLE), ('LINEABOVE', (0, 0), (-1, 0), 0.7, LINE),
                           ('LINEBELOW', (0, -1), (-1, -1), 0.7, LINE), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    return t


def numbered_rows(rows):
    """rows: (badge text, tag line, body text). A purple badge, a small tag and the text, one table row each."""
    def badge(n):
        b = Table([[Paragraph(f'<font name="HeadM" color="#FFFFFF">{html.escape(str(n))}</font>', ParagraphStyle('bdg', parent=S['cell'], alignment=TA_CENTER))]], colWidths=[8 * mm], rowHeights=[6.5 * mm])
        b.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PURPLE), ('ROUNDEDCORNERS', [2, 2, 2, 2]), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
        return b
    t = Table([[badge(n), [Paragraph(html.escape(tag.upper()), LABEL)] + [P(x) for x in text.split('\n\n')]] for n, tag, text in rows], colWidths=[12 * mm, TW - 12 * mm], splitInRow=1)
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), 0.4, LINE), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    return t


def cards(items, border=LINE):
    """Two-column grid of bordered cards; items are (title, [text, ...])."""
    def card(title, texts):
        c = Table([[[Paragraph(rich(title), S['cellb'])] + [Paragraph(rich(x), S['cell']) for x in texts]]], colWidths=[TW / 2 - 4], splitInRow=1)
        c.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1, border), ('ROUNDEDCORNERS', [4, 4, 4, 4]), ('LEFTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
        return c
    rows = [[card(*items[i]), card(*items[i + 1]) if i + 1 < len(items) else ''] for i in range(0, len(items), 2)]
    t = Table(rows, colWidths=[TW / 2] * 2, splitInRow=1); t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    return t


def case_study(cs):
    head = Table([[[Paragraph('CASE STUDY', KICK), Paragraph(rich(cs.get('subtitle') or cs.get('title', ''), color='#FFFFFF'), BTITLE)]]], colWidths=[TW])
    head.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PURPLE), ('LEFTPADDING', (0, 0), (-1, -1), 14), ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]))
    body = [Paragraph(rich(f"**{p['lead']}** {p.get('text', '')}" if p.get('lead') else p.get('text', '')), S['body']) for p in cs.get('paragraphs') or []]
    return [head, Spacer(1, 6)] + body + ([Spacer(1, 4), box([P('**Discussion points:** ' + cs['discussion'])])] if cs.get('discussion') else [])


def main():
    c = printable(json.load(open(sys.argv[1], encoding='utf-8'))); out = sys.argv[2]
    title = c.get('title') or c.get('subject', 'Learning module'); topics = c.get('topics', []); cs = c.get('case_study'); practice = c.get('practice', []); rev = c.get('revision')
    n_top = len(topics)

    def first(cv, doc):
        cv.saveState(); cv.setFillColor(PURPLE); cv.rect(0, H - band, W, band, stroke=0, fill=1)
        lw = 34 * mm; cv.drawImage(LOGO_WHITE, M, H - 19 * mm, lw, lw * 262 / 644, mask='auto'); cv.restoreState()

    def later(cv, doc):
        cv.saveState(); cv.setFillColor(PURPLE); cv.setFont('HeadM', 8); cv.drawRightString(W - M, H - 11 * mm, fit(plain(title).upper(), 'HeadM', 8, TW - 40 * mm))
        cv.setStrokeColor(PURPLE); cv.setLineWidth(0.6); cv.line(M, H - 14 * mm, W - M, H - 14 * mm)
        cv.setStrokeColor(LINE); cv.setLineWidth(0.5); cv.line(M, 14 * mm, W - M, 14 * mm)
        cv.setFont('Body', 7.5); cv.setFillColor(GREY); cv.drawRightString(W - M, 10 * mm, f'Page {doc.page}')
        cv.setFont('HeadM', 7.5); cv.setFillColor(PURPLE); lab = 'Back to contents'; tw = cv.stringWidth(lab, 'HeadM', 7.5); x0 = W / 2 - tw / 2
        cv.drawString(x0, 10 * mm, lab); cv.linkRect('', 'contents', (x0 - 2, 8.5 * mm, x0 + tw + 2, 13 * mm), relative=0, thickness=0); cv.restoreState()

    doc = TopicDoc(out, pagesize=A4, title=plain(title), author='Edwisely', leftMargin=M, rightMargin=M, topMargin=18 * mm, bottomMargin=18 * mm)
    doc.addPageTemplates([PageTemplate('first', [Frame(M, 18 * mm, TW, H - 18 * mm - 30 * mm, id='f1')], onPage=first, onPageEnd=watermark),
                          PageTemplate('later', [Frame(M, 18 * mm, TW, H - 18 * mm - 22 * mm, id='f2')], onPage=later, onPageEnd=watermark)])

    # cover: title, yellow bar and description sit on the purple band; tiles and "what's inside" below it
    bar = Table([['']], colWidths=[26 * mm], rowHeights=[2.2 * mm]); bar.hAlign = 'LEFT'; bar.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), YEL)]))
    head = Table([[[Paragraph(rich(title, color='#FFFFFF'), S['title']), Spacer(1, 8), bar, Spacer(1, 10),
                    Paragraph(rich(c.get('description', ''), color='#D9D0EE'), S['sub'])]]], colWidths=[TW], minRowHeights=[76 * mm])
    head.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    band = max(112 * mm, 30 * mm + head.wrap(TW, H)[1] + 6 * mm)      # a long title or description makes the purple band taller
    inside = [(f'{k:02d}', t.get('title', '')) for k, t in enumerate(topics, 1)] + ([('CS', cs.get('title', ''))] if cs else [])
    grid = Table([[Paragraph(f'<font name="Head" color="#4D2A87">{a}</font>   ' + rich(b), S['cell']) for a, b in inside[i:i + 2]] + [''] * (2 - len(inside[i:i + 2])) for i in range(0, len(inside), 2)] or [['', '']],
                 colWidths=[TW / 2] * 2)      # a module with nothing in it yet still builds (the grid is left out below)
    grid.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.4, LINE), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    units = f'{n_top} Learning Unit{"s" if n_top != 1 else ""}' + (' · 1 Case Study' if cs else '')
    extras = [(k, c[f]) for k, f in (('Estimated study time', 'study_time'), ('Recommended for', 'audience')) if c.get(f)]
    story = [NextPageTemplate('later'), head, Spacer(1, 8 * mm), tiles([('Subject', c.get('subject', '')), ('Topics', units)]), Spacer(1, 6)]
    if inside: story += [Paragraph('WHAT\'S INSIDE', LABEL), grid, Spacer(1, 8)]
    if extras: story += [tiles(extras), Spacer(1, 6)]

    story += [PageBreak()] + contents_block()
    for n, t in enumerate(topics, 1):
        story += [PageBreak(), mark(banner(f'TOPIC {n:02d}', t.get('title', ''), t.get('tagline')), 0, f'{n:02d}  {t.get("title", "")}'), Spacer(1, 8)] + topic_body(t.get('blocks', []), n)
    if cs: story += section_head('APPLIED', 'Case Study: ' + cs.get('title', '')) + safely('The case study', case_study, cs)
    if practice:
        story += section_head('PRACTICE', 'Practice Questions', 'Work through these before checking the model answers that follow.')
        story += safely('The practice questions', lambda: [numbered_rows([(k, p.get('tag', ''), p.get('question', '')) for k, p in enumerate(practice, 1)])])
        story += section_head('SOLUTIONS', 'Model Answers', 'Numbered to match the practice questions.')
        story += safely('The model answers', lambda: [numbered_rows([(k, p.get('tag', ''), p.get('answer', '')) for k, p in enumerate(practice, 1)])])
    if rev:
        story += section_head('RECAP', 'Revision Sheet', 'A fast pass over everything in this module before you move on.')
        if rev.get('concepts'):
            story += [Paragraph('Key concepts at a glance', S['h2'])] + safely('The concept cards', lambda: [cards([(x.get('title', ''), ['• ' + y for y in x.get('points', [])]) for x in rev['concepts']])])
        d = rev.get('distinctions') or {}
        if d.get('rows'): story += [Paragraph('Important distinctions', S['h2'])] + blocks([dict(d, type='table')])
        if rev.get('mistakes'): story += [Paragraph('Common mistakes to avoid', S['h2'])] + safely('The mistakes cards', lambda: [cards([(m.get('title', ''), [m.get('text', '')]) for m in rev['mistakes']], PURPLE)])
        if rev.get('checklist'):
            story += [Paragraph(html.escape(rev.get('checklist_title') or 'Checklist before you move on'), S['h2']),
                      box([Paragraph(f'{k}. ' + rich(x), S['body']) for k, x in enumerate(rev['checklist'], 1)], bar=YEL)]
    doc.multiBuild(story)
    finish(out)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Shared PDF helpers for the GATE and Non-GATE renderers: fonts, styles, rich text with maths,
tables, boxes, images, generic content blocks and the clickable contents machinery.
Text fields support **bold**, *italic*, inline maths $...$ (matplotlib mathtext) and line breaks (
)."""
import json, os, re, sys, hashlib, html, tempfile
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.flowables import Flowable
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                Image, KeepTogether, PageBreak, Preformatted, CondPageBreak, NextPageTemplate)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figures as FIG

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'assets', 'fonts')
for name, f in [('Head', 'Poppins-Bold.ttf'), ('HeadM', 'Poppins-Medium.ttf'), ('HeadR', 'Poppins-Regular.ttf'),
                ('Body', 'DejaVuSans.ttf'), ('BodyB', 'DejaVuSans-Bold.ttf'), ('BodyI', 'DejaVuSans-Oblique.ttf'),
                ('Mono', 'DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONTS, f)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyB', italic='BodyI', boldItalic='BodyB')

PURPLE = colors.HexColor('#4D2A87'); LAV = colors.HexColor('#F0EBFA'); YEL = colors.HexColor('#FFE100')
LINE = colors.HexColor('#D9D0EE'); INK = colors.HexColor('#1F1A2E'); GREY = colors.HexColor('#6B6480')
W, H = A4; M = 18 * mm

S = {
    'title': ParagraphStyle('t', fontName='Head', fontSize=26, leading=31, textColor=colors.white),
    'kicker': ParagraphStyle('k', fontName='HeadM', fontSize=9, leading=12, textColor=colors.white),
    'sub': ParagraphStyle('s', fontName='HeadR', fontSize=11.5, leading=15, textColor=colors.white),
    'h1': ParagraphStyle('h1', fontName='Head', fontSize=17, leading=22, textColor=PURPLE, spaceBefore=10, spaceAfter=6),
    'h2': ParagraphStyle('h2', fontName='Head', fontSize=12.5, leading=16, textColor=INK, spaceBefore=8, spaceAfter=4),
    'body': ParagraphStyle('b', fontName='Body', fontSize=9.6, leading=14, textColor=INK, spaceAfter=5, autoLeading='max'),
    'small': ParagraphStyle('sm', fontName='Body', fontSize=8, leading=11, textColor=GREY),
    'cell': ParagraphStyle('c', fontName='Body', fontSize=8.8, leading=12, textColor=INK),
    'cellh': ParagraphStyle('ch', fontName='HeadM', fontSize=8.8, leading=12, textColor=colors.white),
    'callout': ParagraphStyle('co', fontName='Body', fontSize=9.6, leading=14, textColor=colors.white, autoLeading='max'),
    'tag': ParagraphStyle('tg', fontName='HeadM', fontSize=7.8, leading=10, textColor=INK),
    'mono': ParagraphStyle('m', fontName='Mono', fontSize=8.4, leading=11.5, textColor=INK),
    'subhead': ParagraphStyle('sh', fontName='BodyB', fontSize=9.6, leading=14, textColor=INK, spaceBefore=2, spaceAfter=3),
    'boxtitle': ParagraphStyle('bt', fontName='Head', fontSize=10, leading=14, textColor=PURPLE, spaceAfter=2),
    'figtitle': ParagraphStyle('ft', fontName='HeadM', fontSize=10, leading=13, textColor=PURPLE, spaceBefore=4, spaceAfter=2),
    'cellb': ParagraphStyle('cb', fontName='BodyB', fontSize=8.8, leading=12, textColor=INK),
}
TW = W - 2 * M          # text width
INNER = TW - 22          # width inside a box (bar + paddings)
MATHDIR = os.path.join(tempfile.gettempdir(), 'topicpdf_math'); os.makedirs(MATHDIR, exist_ok=True)


# LaTeX commands that matplotlib's mathtext does not know, and what to draw instead
TEX_FIXES = {r'\land': r'\wedge', r'\lor': r'\vee', r'\lnot': r'\neg', r'\implies': r'\Rightarrow', r'\iff': r'\Leftrightarrow', r'\le': r'\leq', r'\ge': r'\geq',
             r'\ne': r'\neq', r'\dfrac': r'\frac', r'\tfrac': r'\frac', r'\text': r'\mathrm', r'\textrm': r'\mathrm', r'\operatorname': r'\mathrm', r'\dots': r'\ldots',
             r'\bmod': r'\ \mathrm{mod}\ ', r'\pmod': r'\ \mathrm{mod}\ '}


def normalize_tex(tex):
    return re.sub(r'\\[A-Za-z]+', lambda m: TEX_FIXES.get(m.group(0), m.group(0)), tex)


def math_img(tex, size=10.5, display=False, color='#1F1A2E'):
    tex = normalize_tex(tex)
    key = hashlib.md5(f'{tex}|{size}|{display}|{color}'.encode()).hexdigest()
    fn = os.path.join(MATHDIR, key + '.png')
    if not os.path.exists(fn):
        fig = plt.figure(figsize=(0.01, 0.01))
        try:
            fig.text(0, 0, f'${tex}$', fontsize=size * (1.25 if display else 1), color=color)
            fig.savefig(fn, dpi=300, bbox_inches='tight', pad_inches=0.02, transparent=True)
        finally:
            plt.close(fig)
    from PIL import Image as PI
    w, h = PI.open(fn).size
    return fn, w * 72 / 300, h * 72 / 300


def rich(text, size=10.5, color='#1F1A2E'):
    """**bold**, *italic*, $math$ -> reportlab markup."""
    out = []
    for i, part in enumerate(re.split(r'(?<!\\)\$(.+?)(?<!\\)\$', text or '')):
        if i % 2:
            try:
                fn, w, h = math_img(part, size, False, color)
                out.append(f'<img src="{fn}" width="{w:.1f}" height="{h:.1f}" valign="{-h * 0.28:.1f}"/>')
            except Exception:
                out.append(html.escape(part))
        else:
            t = html.escape(part.replace('\\$', '$'))
            t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t); t = re.sub(r'(?<!\*)\*(?!\*)(.+?)\*', r'<i>\1</i>', t)
            out.append(t.replace('\n', '<br/>'))
    return ''.join(out)


def P(text, style='body'): return Paragraph(rich(text), S[style])


def keep(flow):
    flow._keep_next = True; return flow


def styled_table(header, rows, widths=None, total_row=False, avail=None):
    """Purple header, striped rows. total_row=True: last row bold on a darker lavender (Average / Total)."""
    avail = avail or TW
    n = len(header)
    if widths and sum(widths) > avail: widths = [w * avail / sum(widths) for w in widths]
    widths = widths or [avail / n] * n
    body = []
    for i, r in enumerate(rows):
        st_ = S['cellb'] if total_row and i == len(rows) - 1 else S['cell']
        body.append([Paragraph(rich('' if c is None else str(c)), st_) for c in r])
    data = [[Paragraph(rich(h, color='#FFFFFF'), S['cellh']) for h in header]] + body
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [('BACKGROUND', (0, 0), (-1, 0), PURPLE), ('GRID', (0, 0), (-1, -1), 0.5, LINE),
          ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
          ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('BACKGROUND', (0, 1), (-1, -1), colors.white)]
    st += [('BACKGROUND', (0, i), (-1, i), LAV) for i in range(2, len(data), 2)]
    if total_row: st += [('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E6DEF5')), ('LINEABOVE', (0, -1), (-1, -1), 1, PURPLE)]
    t.setStyle(TableStyle(st)); return t


def box(flows, bg=LAV, bar=PURPLE, pad=8, width=TW):
    """Coloured box with a left bar. One flowable per row, so long worked examples split across pages."""
    flows = [f for f in flows if f is not None] or [Spacer(1, 1)]
    rows, k = [], 0
    while k < len(flows):            # a title / "Solution" label never ends a page alone: glue it to what follows
        cell = [flows[k]]
        while getattr(flows[k], '_keep_next', False) and k + 1 < len(flows): k += 1; cell.append(flows[k])
        rows.append([cell if len(cell) > 1 else cell[0]]); k += 1
    t = Table(rows, colWidths=[width])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), bg), ('LINEBEFORE', (0, 0), (0, -1), 3, bar),
                           ('LEFTPADDING', (0, 0), (-1, -1), pad + 2), ('RIGHTPADDING', (0, 0), (-1, -1), pad),
                           ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                           ('TOPPADDING', (0, 0), (-1, 0), pad), ('BOTTOMPADDING', (0, -1), (-1, -1), pad)]))
    return t


def tag(text):
    t = Table([[Paragraph(html.escape(text), S['tag'])]])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), YEL), ('LEFTPADDING', (0, 0), (-1, -1), 5),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 2),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
    t.hAlign = 'LEFT'; return t


def image(path, maxw=None, maxh=115 * mm, width=None, align='CENTER'):
    """Place a PNG. width = fraction of the available width (e.g. 1.0 full, 0.6); otherwise natural size
    from the PNG dpi (figures.py writes 200 dpi), shrunk to fit."""
    from PIL import Image as PI
    maxw = maxw or TW
    pi = PI.open(path); w, h = pi.size; dpi = (pi.info.get('dpi') or (150, 150))[0] or 150
    nat_w, nat_h = w * 72 / dpi, h * 72 / dpi
    if width: sc = maxw * float(width) / nat_w
    else: sc = min(1.0, maxw / nat_w)
    sc = min(sc, maxh / nat_h) if nat_h * sc > maxh else sc
    im = Image(path, nat_w * sc, nat_h * sc); im.hAlign = align; return im


def figure_path(b):
    """Path of a figure/image block, rendering figures.py specs on demand."""
    if b.get('kind'): return FIG.render(b['kind'], b.get('spec', {}))
    return b.get('path')


def blocks(items, avail=None):
    """Render BLOCKs (see references/content_schema.md). avail = width available (inside a box it is smaller)."""
    avail = avail or TW
    out = []
    for b in items:
        if isinstance(b, str): b = {'type': 'para', 'text': b}
        t = b.get('type', 'para')
        if t == 'para': out.append(P(b['text']))
        elif t == 'subhead': out.append(keep(Paragraph(rich(b['text']), S['subhead'])))
        elif t == 'bullets':
            for it in b['items']:
                out.append(Paragraph(rich(it), ParagraphStyle('bl', parent=S['body'], leftIndent=12, bulletIndent=2),
                                     bulletText='•'))
        elif t == 'numbered':
            for k, it in enumerate(b['items'], 1):
                out.append(Paragraph(rich(it), ParagraphStyle('nl', parent=S['body'], leftIndent=14, bulletIndent=0),
                                     bulletText=f'{k}.'))
        elif t == 'formula':
            try:
                fn, w, h = math_img(b['latex'], 11, True)
                if w > avail: h, w = h * avail / w, avail
                im = Image(fn, w, h); im.hAlign = 'CENTER'
                out += [Spacer(1, 3), im, Spacer(1, 5)]
            except Exception:       # a formula the maths renderer cannot draw is shown as plain text instead of stopping the PDF
                out.append(Paragraph(html.escape(b['latex']), S['mono']))
        elif t == 'table':
            out += [styled_table(b['header'], b['rows'], b.get('widths'), b.get('total_row', False), avail), Spacer(1, 6)]
        elif t == 'code':
            chars = int((avail - 24) / (S['mono'].fontSize * 0.602))      # long lines are wrapped instead of running out of the box
            out += [box([Preformatted(b['text'], S['mono'], maxLineLength=chars, splitChars=' ')], bg=colors.HexColor('#F7F5FC'), bar=LINE, width=avail), Spacer(1, 6)]
        elif t == 'callout':
            out += [box([Paragraph(rich(b['text'], color='#FFFFFF'), S['callout'])], bg=PURPLE, bar=YEL, width=avail), Spacer(1, 6)]
        elif t in ('note', 'trap'):
            title = b.get('title', 'Common GATE trap' if t == 'trap' else None)
            inner = ([keep(Paragraph(html.escape(title), S['boxtitle']))] if title else []) + \
                    ([P(x) for x in b['text'].split('\n\n')] if b.get('text') else []) + blocks(b.get('blocks', []), INNER)
            out += [box(inner, width=avail), Spacer(1, 6)]
        elif t in ('image', 'figure'):
            fp = figure_path(b)
            wd = b.get('width') or (1.0 if b.get('kind') in ('gantt', 'timeline') else None)
            grp = ([Paragraph(rich(b['title']), S['figtitle'])] if b.get('title') else []) + \
                  [image(fp, avail, width=wd, maxh=b.get('max_height_mm', 115) * mm)] + ([P(b['caption'], 'small')] if b.get('caption') else [])
            for f in grp[:-1]: keep(f)      # inside a box, box() glues these to the next flowable (a KeepTogether cannot sit in a table cell)
            out += ([KeepTogether(grp)] if len(grp) > 1 and avail >= TW else grp) + [Spacer(1, 4)]
        elif t == 'example':
            title = re.sub(r'^(worked example\s*[:\-–—]*\s*)+', '', b.get('title') or '', flags=re.I)     # the label is added here, so a title must not repeat it
            inner = [keep(Paragraph(f'<font name="Head" color="#4D2A87">Worked example{": " + html.escape(title) if title else ""}</font>', S['body']))]
            inner += text_or_blocks(b.get('problem'))
            inner.append(keep(Paragraph('<font name="HeadM" color="#4D2A87">Solution</font>', S['body'])))
            inner += text_or_blocks(b.get('solution'))
            out += [box(inner, width=avail), Spacer(1, 8)]
        elif t == 'spacer': out.append(Spacer(1, b.get('height', 6)))
        elif t == 'pagebreak': out.append(PageBreak())
        else: raise ValueError(f'unknown block type {t!r}')
    return out


def text_or_blocks(x, avail=INNER):
    """Example problem/solution: a string (blank line = new paragraph) or a list of BLOCKs."""
    if not x: return []
    if isinstance(x, str): return [P(p) for p in x.split('\n\n')]
    return blocks(x, avail)




class TopicDoc(BaseDocTemplate):
    """Registers every marked heading as a clickable contents entry and a PDF sidebar bookmark."""
    def afterFlowable(self, f):
        e = getattr(f, '_toc', None)
        if not e: return
        level, text, key = e
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=max(level, 0), closed=False)
        if level >= 0: self.notify('TOCEntry', (level, text, self.page, key))


class Anchor(Flowable):
    """Zero-size flowable that only sets a bookmark (used for the Contents page itself)."""
    def __init__(self, key, text): super().__init__(); self._toc = (-1, text, key); self.width = self.height = 0
    def wrap(self, *a): return 0, 0
    def draw(self): pass


def plain(t):
    t = re.sub(r'\$(.+?)\$', lambda m: re.sub(r'[\\{}_^]|mathrm', '', m.group(1)), t or '')
    return re.sub(r'\*\*|(?<!\*)\*(?!\*)', '', t)


_nkey = [0]


def mark(par, level, text):
    """Tag a heading paragraph for the contents page (level 0 = section, 1 = sub-section)."""
    _nkey[0] += 1; par._toc = (level, plain(text), f'sec{_nkey[0]}'); return par


def contents_block():
    toc = TableOfContents(dotsMinLevel=0)
    toc.levelStyles = [
        ParagraphStyle('toc0', fontName='Head', fontSize=10.5, leading=15, textColor=PURPLE, spaceBefore=6, leftIndent=0, firstLineIndent=0),
        ParagraphStyle('toc1', fontName='Body', fontSize=9, leading=12.5, textColor=INK, leftIndent=16, firstLineIndent=0)]
    return [Anchor('contents', 'Contents'), Paragraph('Contents', S['h1']),
            Paragraph('Click any line to jump to that page. Every page has a "Back to contents" link in its footer, and the PDF sidebar shows the same outline.', S['small']), Spacer(1, 4), toc]


ASSET = os.path.join(HERE, 'assets')
LOGO_WHITE = os.path.join(ASSET, 'edwisely_logo_white.png')


def watermark(cv, doc=None):
    """Faint centred Edwisely logo, drawn at the end of every page."""
    ww = 120 * mm; wh = ww * 262 / 644
    cv.saveState(); cv.drawImage(os.path.join(ASSET, 'edwisely_watermark.png'), (W - ww) / 2, (H - wh) / 2 - 10 * mm, ww, wh, mask='auto'); cv.restoreState()

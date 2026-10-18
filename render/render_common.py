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
import reportlab.platypus.paragraph as _para
_para.paraFontSizeHeightOffset = 0       # a first line starts below its tallest part (inline maths), not one font size down: maths never pokes out above
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figures as FIG
import tex as TEX

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
    'h1': ParagraphStyle('h1', fontName='Head', fontSize=17, leading=22, textColor=PURPLE, spaceBefore=10, spaceAfter=6, keepWithNext=1),
    'h2': ParagraphStyle('h2', fontName='Head', fontSize=12.5, leading=16, textColor=INK, spaceBefore=8, spaceAfter=4, keepWithNext=1),
    'body': ParagraphStyle('b', fontName='Body', fontSize=9.6, leading=14, textColor=INK, spaceAfter=5, autoLeading='max'),
    'small': ParagraphStyle('sm', fontName='Body', fontSize=8, leading=11, textColor=GREY, autoLeading='max'),
    'cell': ParagraphStyle('c', fontName='Body', fontSize=8.8, leading=12, textColor=INK, autoLeading='max'),
    'cellh': ParagraphStyle('ch', fontName='HeadM', fontSize=8.8, leading=12, textColor=colors.white, autoLeading='max'),
    'callout': ParagraphStyle('co', fontName='Body', fontSize=9.6, leading=14, textColor=colors.white, autoLeading='max'),
    'tag': ParagraphStyle('tg', fontName='HeadM', fontSize=7.8, leading=10, textColor=INK, autoLeading='max'),
    'mono': ParagraphStyle('m', fontName='Mono', fontSize=8.4, leading=11.5, textColor=INK),
    'subhead': ParagraphStyle('sh', fontName='BodyB', fontSize=9.6, leading=14, textColor=INK, spaceBefore=2, spaceAfter=3, autoLeading='max', keepWithNext=1),
    'boxtitle': ParagraphStyle('bt', fontName='Head', fontSize=10, leading=14, textColor=PURPLE, spaceAfter=2, autoLeading='max', keepWithNext=1),
    'figtitle': ParagraphStyle('ft', fontName='HeadM', fontSize=10, leading=13, textColor=PURPLE, spaceBefore=4, spaceAfter=2, keepWithNext=1),
    'cellb': ParagraphStyle('cb', fontName='BodyB', fontSize=8.8, leading=12, textColor=INK, autoLeading='max'),
}
TW = W - 2 * M          # text width
INNER = TW - 22          # width inside a box (bar + paddings)
MATHDIR = os.path.join(tempfile.gettempdir(), 'topicpdf_math'); os.makedirs(MATHDIR, exist_ok=True)


normalize_tex = TEX.normalize      # LaTeX that mathtext cannot draw, rewritten into what it can (render/tex.py)


def math_img(tex, size=10.5, display=False, color='#1F1A2E'):
    tex = TEX.normalize(tex) if display else TEX.inline(tex)
    key = hashlib.md5(f'{tex}|{size}|{display}|{color}|crop'.encode()).hexdigest()
    fn = os.path.join(MATHDIR, key + '.png')
    if not os.path.exists(fn):
        fig = plt.figure(figsize=(0.01, 0.01))
        try:
            fig.text(0, 0, f'${tex}$', fontsize=size * (1.25 if display else 1), color=color)
            fig.savefig(fn, dpi=300, bbox_inches='tight', pad_inches=0.1, transparent=True)
        finally:
            plt.close(fig)
        from PIL import Image as PI          # the tight box can cut off accents and stacked tops (\overset, \dot): crop to the ink instead
        im = PI.open(fn); l, t, r, b = im.getbbox() or (0, 0) + im.size
        im.crop((max(l - 6, 0), max(t - 6, 0), min(r + 6, im.width), min(b + 6, im.height))).save(fn)
    from PIL import Image as PI
    w, h = PI.open(fn).size
    return fn, w * 72 / 300, h * 72 / 300


SYMBOLS = {r'\times': '×', r'\cdot': '·', r'\wedge': '∧', r'\vee': '∨', r'\neg': '¬', r'\leq': '≤', r'\geq': '≥', r'\neq': '≠', r'\Rightarrow': '⇒', r'\rightarrow': '→',
           r'\to': '→', r'\pm': '±', r'\ldots': '…', r'\sum': 'Σ', r'\pi': 'π', r'\mu': 'µ', r'\Omega': 'Ω', r'\alpha': 'α', r'\beta': 'β', r'\theta': 'θ', r'\lambda': 'λ',
           r'\over': '/', r'\mid': '|', r'\vert': '|', r'\Vert': '‖', r'\in': '∈', r'\infty': '∞', r'\Leftrightarrow': '⇔', r'\leftarrow': '←', r'\approx': '≈'}


def frac_text(t):
    """\\frac{a}{b} -> a/b, with brackets round a part that is not a single token."""
    p = lambda x: x if re.fullmatch(r'\w*', x) else f'({x})'
    for _ in range(3): t = re.sub(r'\\frac\s*' + TEX.ARG + r'\s*' + TEX.ARG, lambda m: p(m.group(1)) + '/' + p(m.group(2)), t)
    return t


def tex_text(tex):
    """Readable plain text for maths the renderer cannot draw, instead of showing raw LaTeX."""
    t = frac_text(normalize_tex(tex))
    t = re.sub(r'\\(?:mathrm|text|textbf|mathbf|mathit|mathbb|mathcal|mathsf|operatorname)\{([^{}]*)\}', r'\1', t)
    t = re.sub(r'(?<!\\)&', ' ', re.sub(r'\\(?:begin|end)\{[^{}]*\}', '', t).replace('\\\\', '; '))      # column marks; \& stays a literal &
    t = re.sub(r'\\[A-Za-z]+', lambda m: SYMBOLS.get(m.group(0)) or FIG.GREEK.get(m.group(0)[1:], ''), t)
    t = re.sub(r'\\([{}|%#&$])', r'\1', re.sub(r'\\[ ,;:!]', ' ', t))         # spacing commands and escaped symbols
    return re.sub(r'\s+', ' ', t.replace('{', '').replace('}', '')).strip()


TEXT_KEYS = {'title', 'subtitle', 'tagline', 'subject', 'paper', 'topic_name', 'syllabus_line', 'heading', 'text', 'caption', 'tag', 'source',
             'question', 'answer', 'answer_range', 'qtype', 'level', 'lead', 'description', 'discussion', 'marking', 'duration',
             'checklist_title', 'pyq_note', 'q', 'a', 'latex', 'study_time', 'audience'}


def as_text(x):
    if isinstance(x, list): return '\n\n'.join(as_text(v) for v in x)
    if isinstance(x, dict): return as_text(x.get('text') or ' '.join(as_text(v) for v in x.values()))
    return '' if x is None else str(x)


def printable(x, key=None):
    """The content with every field the renderers print as text made a string, whatever the model put there.
    Figure specs are left alone (figures.py reads their own types)."""
    if key == 'spec': return x
    if key in TEXT_KEYS and x is not None and not isinstance(x, str): return as_text(x)
    if isinstance(x, dict):            # an empty text field is left out, so the renderer's default wording applies
        return {k: printable(v, k) for k, v in x.items() if not (k in TEXT_KEYS and (v is None or v == ''))}
    if isinstance(x, list): return [printable(v) for v in x]
    return x


MONEY = re.compile(r'(?<!\\)\$(?=\d[\d.,]*\s[^$\\]*?\b[A-Za-z]{3})')       # "costs $5 and $10": money, not maths


def math_split(text):
    """[text, maths, text, maths, ...]; $$x$$ in running text is maths like $x$."""
    return re.split(r'(?<!\\)\$(.+?)(?<!\\)\$', MONEY.sub(r'\\$', text.replace('$$', '$')), flags=re.S)


ITALIC = re.compile(r'(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])')       # *x* only: never the stars of a*b*, 2*3 or (a|b)*


def rich(text, size=10.5, color='#1F1A2E', max_w=INNER):
    """**bold**, *italic*, `code`, $math$ -> reportlab markup. Maths wider than max_w (the room it has) is scaled down to fit."""
    if not isinstance(text, str): text = '\n'.join(map(str, text)) if isinstance(text, list) else '' if text is None else str(text)
    out, bold = [], False                     # **bold** may contain $maths$, so its state runs across the pieces

    def star2(m):                             # ** opens before a non-space and closes after one, never inside x ** 2 or a**b
        nonlocal bold
        before, after = m.string[m.start() - 1:m.start()], m.string[m.end():m.end() + 1]
        if not bold and not after.isspace() and not re.match(r'[\w*]', before): bold = True; return '<b>'
        if bold and not before.isspace() and not re.match(r'[\w*]', after): bold = False; return '</b>'
        return m.group(0)

    for j, chunk in enumerate(re.split(r'`([^`\n]+)`', text)):         # `code` first: its * and $ are typed characters
        if j % 2: out.append(f'<font name="Mono">{html.escape(chunk)}</font>'); continue
        for i, part in enumerate(math_split(chunk)):
            if i % 2:
                part = ' '.join(part.split())                        # maths written over several lines
                try:
                    fn, w, h = math_img(part, size, False, color)
                    if max_w and w > max_w: w, h = max_w, h * max_w / w
                    out.append(f'<img src="{fn}" width="{w:.1f}" height="{h:.1f}" valign="{-h * 0.28:.1f}"/>')
                except Exception:
                    out.append(html.escape(tex_text(part)))
            else:
                t = ITALIC.sub(r'<i>\1</i>', html.escape(part.replace('\\$', '$')))
                out.append(re.sub(r'\*\*', star2, t).replace('\n', '<br/>'))
    return ''.join(out) + ('</b>' if bold else '')


def fit(text, font, size, width):
    """text cut with an ellipsis so that it is at most `width` points wide."""
    if pdfmetrics.stringWidth(text, font, size) <= width: return text
    while text and pdfmetrics.stringWidth(text + '…', font, size) > width: text = text[:-1]
    return text.rstrip() + '…'


def P(text, style='body'): return Paragraph(rich(text), S[style])


def keep(flow):
    flow._keep_next = True; flow.keepWithNext = True; return flow      # _keep_next inside box(), keepWithNext on the page


def styled_table(header, rows, widths=None, total_row=False, avail=None):
    """Purple header, striped rows. total_row=True: last row bold on a darker lavender (Average / Total)."""
    """No header: the rows alone. A row longer than the header keeps its cells (the header gets empty ones)."""
    avail = avail or TW
    rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rows]
    n = max([len(header or [])] + [len(r) for r in rows])
    if not (widths and len(widths) == n and all(isinstance(w, (int, float)) and w >= 30 for w in widths)): widths = [avail / n] * n    # widths that cannot be used
    if sum(widths) > avail: widths = [w * avail / sum(widths) for w in widths]
    body = []
    for i, r in enumerate(rows):
        r = r + [''] * (n - len(r))                     # every row as wide as the widest
        st_ = S['cellb'] if total_row and i == len(rows) - 1 else S['cell']
        body.append([Paragraph(rich('' if c is None else str(c), max_w=w - 12), st_) for c, w in zip(r, widths)])
    head = [[Paragraph(rich(h, color='#FFFFFF', max_w=w - 12), S['cellh']) for h, w in zip(list(header) + [''] * n, widths)]] if any(not blank(h) for h in header or []) else []
    data = head + body
    t = Table(data, colWidths=widths, repeatRows=len(head), splitInRow=1)       # splitInRow: a cell taller than a page goes on over the next
    st = [('GRID', (0, 0), (-1, -1), 0.5, LINE),
          ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
          ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('BACKGROUND', (0, 0), (-1, -1), colors.white)]
    st += [('BACKGROUND', (0, 0), (-1, 0), PURPLE)] if head else []
    st += [('BACKGROUND', (0, i), (-1, i), LAV) for i in range(len(head) + 1, len(data), 2)]
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
    t = Table(rows, colWidths=[width], splitInRow=1)        # a part taller than a page (long code, a long note) goes on over the next
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
    if width: sc = min(maxw * float(width) / nat_w, 1.15)      # never blow a small drawing up: its text would grow with it
    else: sc = min(1.0, maxw / nat_w)
    sc = min(sc, maxh / nat_h) if nat_h * sc > maxh else sc
    if sc < 0.5: warn(f'A figure had to be shrunk to {sc:.0%} of its size to fit the page; its text may be hard to read')
    im = Image(path, nat_w * sc, nat_h * sc); im.hAlign = align; return im


def figure_path(b):
    """PNG of a figure object {kind, spec}, drawn by figures.py (cached)."""
    return FIG.render(b['kind'], b.get('spec', {}))


WARNINGS = []      # what had to be left out of the PDF; printed as JSON at the end so the pipeline can show it


def warn(text):
    if text not in WARNINGS: WARNINGS.append(text)


def safely(what, fn, *args):
    """Flowables from fn(*args), or none (with a warning) if this part cannot be drawn: one bad part never stops the PDF."""
    try: return fn(*args)
    except Exception as e:
        warn(f'{what} could not be drawn and was left out ({type(e).__name__}: {str(e)[:120]})'); return []


def finish(out):
    print(json.dumps({'written': out, 'warnings': WARNINGS}))


BLOCK_FIELD = {'para': 'text', 'subhead': 'text', 'bullets': 'items', 'numbered': 'items', 'formula': 'latex', 'code': 'text', 'callout': 'text'}


def blocks(items, avail=None):
    """Render BLOCKs (prompts/gate/content_schema.md), each on its own. avail = width available (inside a box it is smaller)."""
    out = []
    for b in items or []:
        if isinstance(b, str): b = {'type': 'para', 'text': b}
        if isinstance(b, dict): out += safely(f'A "{b.get("type", "para")}" block', block, b, avail or TW)
    return out


def block(b, avail):
    out = []
    t = b.get('type', 'para')
    boxed = avail < TW                      # inside a box: page-level layout (breaks, big gaps) does not apply
    if t in ('bullets', 'numbered'): b = dict(b, items=[x for x in b.get('items') or [] if not blank(x)])
    if (t in BLOCK_FIELD and blank(b.get(BLOCK_FIELD[t]))) or (t == 'table' and not b.get('rows')) or (boxed and t in ('spacer', 'pagebreak')) or \
       (t in ('note', 'trap') and blank(b.get('text')) and not b.get('blocks')) or (t == 'example' and blank(b.get('problem')) and blank(b.get('solution'))):
        return out     # nothing to show
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
        out.append(Spacer(1, 3))
        for line in TEX.lines(b['latex']):      # rows of align/aligned, or rows split by \\, each on its own line
            try:
                fn, w, h = math_img(line, 11, True)
                if w > 2 * avail: warn('A formula had to be shrunk to under half its size to fit the page; it may be hard to read')
                if w > avail: h, w = h * avail / w, avail
                im = Image(fn, w, h); im.hAlign = 'CENTER'
                out += [im, Spacer(1, 2)]
            except Exception:   # a formula the maths renderer cannot draw is shown as plain text instead of stopping the PDF
                out.append(Paragraph(html.escape(tex_text(line)), S['body']))
        out.append(Spacer(1, 3))
    elif t == 'table':
        out += [styled_table(b.get('header'), b['rows'], b.get('widths'), b.get('total_row', False), avail), Spacer(1, 6)]
    elif t == 'code':
        chars = int((avail - 24) / (S['mono'].fontSize * 0.602))      # long lines are wrapped instead of running out of the box
        out += [box([Preformatted(b['text'].expandtabs(4), S['mono'], maxLineLength=chars, splitChars=' ')], bg=colors.HexColor('#F7F5FC'), bar=LINE, width=avail), Spacer(1, 6)]
    elif t == 'callout':
        out += [box([Paragraph(rich(b['text'], color='#FFFFFF'), S['callout'])], bg=PURPLE, bar=YEL, width=avail), Spacer(1, 6)]
    elif t in ('note', 'trap'):
        title = b.get('title', 'Common GATE trap' if t == 'trap' else None)
        inner = ([keep(Paragraph(html.escape(title), S['boxtitle']))] if title else []) + \
                ([P(x) for x in b['text'].split('\n\n')] if b.get('text') else []) + blocks(b.get('blocks', []), avail - 22)
        out += [box(inner, width=avail), Spacer(1, 6)]
    elif t == 'figure':
        fp = figure_path(b)
        wd = b.get('width') or (1.0 if b.get('kind') in ('gantt', 'timeline') else None)
        grp = ([Paragraph(rich(b['title']), S['figtitle'])] if b.get('title') else []) + \
              [image(fp, avail, width=wd, maxh=b.get('max_height_mm', 115) * mm)] + ([P(b['caption'], 'small')] if b.get('caption') else [])
        for f in grp[:-1]: keep(f)      # inside a box, box() glues these to the next flowable (a KeepTogether cannot sit in a table cell)
        out += ([KeepTogether(grp)] if len(grp) > 1 and avail >= TW else grp) + [Spacer(1, 4)]
    elif t == 'example':
        title = re.sub(r'^((worked )?example\s*[:\-–—]*\s*)+', '', b.get('title') or '', flags=re.I)     # the label is added here, so a title must not repeat it
        inner = [keep(Paragraph(f'<font name="Head" color="#4D2A87">Worked example{": " + html.escape(title) if title else ""}</font>', S['body']))]
        inner += text_or_blocks(b.get('problem'), avail - 22)
        inner.append(keep(Paragraph('<font name="HeadM" color="#4D2A87">Solution</font>', S['body'])))
        inner += text_or_blocks(b.get('solution'), avail - 22)
        out += [box(inner, width=avail), Spacer(1, 8)]
    elif t == 'spacer': out.append(Spacer(1, min(float(b.get('height') or 6), 50)))
    elif t == 'pagebreak': out.append(PageBreak())
    else: raise ValueError(f'unknown block type {t!r}')
    return out


def blank(x): return not (x.strip() if isinstance(x, str) else x)


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
        if level >= 0: self.notify('TOCEntry', (level, html.escape(text), self.page, key))      # the contents page reads markup


class Anchor(Flowable):
    """Zero-size flowable that only sets a bookmark (used for the Contents page itself)."""
    def __init__(self, key, text): super().__init__(); self._toc = (-1, text, key); self.width = self.height = 0
    def wrap(self, *a): return 0, 0
    def draw(self): pass


def plain(t):
    """A heading as plain text (contents, PDF sidebar, page header): maths as readable text, no markdown."""
    parts = math_split(t or '')
    t = ''.join(tex_text(p) if i % 2 else ITALIC.sub(r'\1', p.replace('\\$', '$')) for i, p in enumerate(parts))
    return re.sub(r'(?<![\w*])\*\*(?=\S)|(?<=\S)\*\*(?![\w*])|`', '', t)


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

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
import matplotlib.figure, matplotlib.font_manager, matplotlib.mathtext
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


MATHTEXT = matplotlib.mathtext.MathTextParser('path')
MATH_PAD = 2.0          # points above and below a formula's box, so accents and stacked tops are never cut
MATH_SIDE = 0.8         # points left and right: enough for an italic overhang, without a gap around inline maths


def math_img(tex, size=10.5, display=False, color='#1F1A2E'):
    """PNG of one formula and its size in points: (file, width, height, depth). The image is the formula's own box as
    mathtext measures it (padded), not a crop to the ink, so the baseline is known: inline maths sits on the text line,
    and a lone superscript (m$^3$) stays raised."""
    tex = TEX.display(tex) if display else TEX.inline(tex)
    fs = size * (1.25 if display else 1)
    w, h, d = MATHTEXT.parse(f'${tex}$', dpi=72, prop=matplotlib.font_manager.FontProperties(size=fs))[:3]    # raises on maths it cannot draw
    W, H = w + 2 * MATH_SIDE, h + 2 * MATH_PAD
    fn = os.path.join(MATHDIR, hashlib.md5(f'{tex}|{fs}|{color}|box'.encode()).hexdigest() + '.png')
    if not os.path.exists(fn):
        fig = matplotlib.figure.Figure(figsize=(W / 72, H / 72))
        fig.text(MATH_SIDE / W, (MATH_PAD + d) / H, f'${tex}$', fontsize=fs, color=color)
        fig.savefig(fn, dpi=300, transparent=True)
    return fn, W, H, d + MATH_PAD


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
        for i, part in enumerate(math_split(TEX.plain(chunk))):          # units and powers outside maths made printable first
            if i % 2:
                part = ' '.join(part.split())                        # maths written over several lines
                try:
                    fn, w, h, d = math_img(part, size, False, color)
                    if max_w and w > max_w: w, h, d = max_w, h * max_w / w, d * max_w / w
                    out.append(f'<img src="{fn}" width="{w:.1f}" height="{h:.1f}" valign="{-d:.1f}"/>')
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


def text_widths(cell, size):
    """(whole width, widest unbreakable piece) of a table cell in points: words of text, and each inline formula as drawn."""
    parts = math_split(TEX.plain(str(cell or '')))
    words = [pdfmetrics.stringWidth(w, 'BodyB', size) for p in parts[0::2] for w in plain(p).split()]
    maths = []
    for m in parts[1::2]:
        try: maths.append(MATHTEXT.parse(f'${TEX.inline(" ".join(m.split()))}$', dpi=72, prop=matplotlib.font_manager.FontProperties(size=size * 1.1))[0])
        except Exception: maths.append(pdfmetrics.stringWidth(tex_text(m), 'Body', size))
    whole = sum(pdfmetrics.stringWidth(plain(p), 'Body', size) for p in parts[0::2]) + sum(maths)
    return whole, max(words + maths, default=0)


def column_widths(cols, avail, size=None):
    """Column widths that follow the content: every column at least as wide as its longest word or formula (so nothing is
    broken in the middle), the rest of the room shared by how much each column holds. When even those do not fit, the
    font steps down (to 7 pt) before a word has to break. Returns (widths, font size)."""
    size = size or S['cell'].fontSize
    sizes = [[text_widths(c, size) for c in col] for col in cols]
    longest = [min(max(w for _, w in col) + 13, avail * 0.6) for col in sizes]        # a huge formula is scaled, not given the table
    full = [max(w for w, _ in col) + 13 for col in sizes]
    if sum(longest) > avail and size > 7: return column_widths(cols, avail, max(7, size * avail / sum(longest) - 0.1))
    if sum(full) <= avail: return [w * avail / sum(full) for w in full], size
    spare = max(avail - sum(longest), 0)
    extra = [max(f - l, 0) for f, l in zip(full, longest)]
    return [l + spare * e / (sum(extra) or 1) for l, e in zip(longest, extra)], size


def styled_table(header, rows, widths=None, total_row=False, avail=None):
    """Purple header, striped rows. total_row=True: last row bold on a darker lavender (Average / Total)."""
    """No header: the rows alone. A row longer than the header keeps its cells (the header gets empty ones)."""
    avail = avail or TW
    rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rows]
    n = max([len(header or [])] + [len(r) for r in rows])
    cols = [[(list(header or []) + [''] * n)[j]] + [(r + [''] * n)[j] for r in rows] for j in range(n)]
    size = S['cell'].fontSize
    if not (widths and len(widths) == n and all(isinstance(w, (int, float)) and w >= 30 for w in widths)):     # widths that cannot be used
        widths, size = column_widths(cols, avail)
    if sum(widths) > avail: widths = [w * avail / sum(widths) for w in widths]
    cell, cellb, cellh = (ParagraphStyle(f'{s.name}{size}', parent=s, fontSize=size, leading=size * 1.36) for s in (S['cell'], S['cellb'], S['cellh']))
    body = []
    for i, r in enumerate(rows):
        r = r + [''] * (n - len(r))                     # every row as wide as the widest
        st_ = cellb if total_row and i == len(rows) - 1 else cell
        body.append([Paragraph(rich('' if c is None else str(c), size * 1.1, max_w=w - 12), st_) for c, w in zip(r, widths)])
    head = [[Paragraph(rich(h, size * 1.1, color='#FFFFFF', max_w=w - 12), cellh) for h, w in zip(list(header) + [''] * n, widths)]] if any(not blank(h) for h in header or []) else []
    data = head + body
    t = Table(data, colWidths=widths, repeatRows=len(head), splitInRow=1)       # splitInRow: a cell taller than a page goes on over the next
    st = [('GRID', (0, 0), (-1, -1), 0.5, LINE),
          ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
          ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('BACKGROUND', (0, 0), (-1, -1), colors.white)]
    st += [('BACKGROUND', (0, 0), (-1, 0), PURPLE)] if head else []
    st += [('BACKGROUND', (0, i), (-1, i), LAV) for i in range(len(head) + 1, len(data), 2)]
    if total_row: st += [('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E6DEF5')), ('LINEABOVE', (0, -1), (-1, -1), 1, PURPLE)]
    t.setStyle(TableStyle(st)); return t


class Box(Flowable):
    """Coloured box with a left bar around a list of flowables. It splits across pages only between its items, or inside
    an item that can split itself (a long paragraph, table or code), and never after an item marked keep() (a box title,
    "Solution", a figure title): such an item moves to the next page with what follows. When nothing fits, the whole box
    moves on, so a page never ends in an empty strip of box or a lone title."""

    def __init__(self, flows, bg=LAV, bar=PURPLE, pad=8, width=TW, border=None):
        super().__init__()
        self.flows, self.bg, self.bar, self.pad, self.width, self.border = [f for f in flows if f is not None] or [Spacer(1, 1)], bg, bar, pad, width, border
        self.inner = width - 2 * pad - 2

    def _sizes(self, avail_h=1e6):
        out = []
        for k, f in enumerate(self.flows):
            w, h = f.wrap(self.inner, avail_h)
            gap = (f.getSpaceAfter() if k < len(self.flows) - 1 else 0) + (f.getSpaceBefore() if k else 0)
            out.append((w, h, gap))
        return out

    def wrap(self, aw, ah):
        self.sizes = self._sizes(ah)
        self.height = 2 * self.pad + sum(h + g for _, h, g in self.sizes)
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState(); c.setFillColor(self.bg); c.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        if self.border: c.setStrokeColor(self.border); c.setLineWidth(0.8); c.rect(0, 0, self.width, self.height, stroke=1, fill=0)
        if self.bar: c.setStrokeColor(self.bar); c.setLineWidth(3); c.line(1.5, 0, 1.5, self.height)
        c.restoreState()
        y, last = self.height - self.pad, len(self.flows) - 1
        for k, (f, (w, h, _)) in enumerate(zip(self.flows, self.sizes)):
            y -= h + (f.getSpaceBefore() if k else 0)
            f.drawOn(c, self.pad + 2, y, _sW=self.inner - w)
            y -= f.getSpaceAfter() if k < last else 0

    def split(self, aw, ah):
        room, used, taken, rest = ah - 2 * self.pad, 0, [], list(self.flows)
        while rest:
            f = rest[0]
            _, h = f.wrap(self.inner, room - used)
            gap = f.getSpaceBefore() if taken else 0
            if used + gap + h <= room:
                taken.append(rest.pop(0)); used += gap + h + f.getSpaceAfter(); continue
            parts = f.split(self.inner, room - used - gap) if room - used - gap > 30 else []
            if len(parts) > 1: taken.append(parts[0]); rest[0:1] = parts[1:]
            break
        while taken and getattr(taken[-1], '_keep_next', False): rest.insert(0, taken.pop())     # a title never ends a page
        if not taken or not rest: return []
        return [Box(part, self.bg, self.bar, self.pad, self.width, self.border) for part in (taken, rest)]


def box(flows, bg=LAV, bar=PURPLE, pad=8, width=TW):
    return Box(flows, bg, bar, pad, width)


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
    sc = max(sc, min(0.8, maxw / nat_w))                        # nor shrink it below 80 %: its 8-9 pt labels stay readable in print
    sc = min(sc, maxh / nat_h) if nat_h * sc > maxh else sc
    if sc < 0.7: warn(f'A figure had to be shrunk to {sc:.0%} of its size to fit the page; its text may be hard to read')
    im = Image(path, nat_w * sc, nat_h * sc); im.hAlign = align; return im


FIGURES = {'section': None, 'n': 0}       # figures of the notes are numbered through the PDF (Figure 3), so the text can refer to them


def figure_section(label):
    """A new notes section starts (None: the notes are over, questions are not numbered)."""
    FIGURES['section'] = label
    DEFINED.clear()                     # a new section explains its symbols again


def figure_number():
    if not FIGURES['section']: return ''
    FIGURES['n'] += 1
    return f"Figure {FIGURES['n']}"


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


LEAK = re.compile(r'\\[A-Za-z]{2,}|\w\^|\^\{|_\{|(?<!\\)\$|\bNone\b(?!\s+(?:of|is|are|the|can))|\bnan\b|"(?:type|latex|blocks)"\s*:|\{\{|\}\}')


def pdf_checks(path, min_fill=0.55):
    """The finished PDF read back: raw LaTeX, code or JSON that reached the page, and pages left mostly empty in the middle
    of a part (a figure or box that could not fit, pushed to the next page). The last line of defence for problems no
    earlier check knows about. Returns warnings."""
    import fitz
    doc, out, leaks = fitz.open(path), [], []
    top, bottom = 18 * mm, H - 18 * mm                  # the body frame, below the header band and above the footer
    def starts_part(page):                              # a page that opens a numbered part ("6. Sample paper") follows a deliberate break
        spans = [s for b in page.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans'] if top <= s['bbox'][1] < bottom]
        return bool(spans) and spans[0]['size'] >= 15 and re.match(r'\d+\.\s', spans[0]['text'].strip() or 'x')
    for i, page in enumerate(doc):
        text = '\n'.join(s['text'] for b in page.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']
                         if 'Mono' not in s['font'])                       # code is shown as typed: its \ and $ are not leaks
        leaks += [f'page {i + 1}: "{m.group(0)}"' for m in LEAK.finditer(re.sub(r'Page \d+|Back to contents', '', text))]
        if 0 < i < doc.page_count - 1 and not starts_part(doc[i + 1]):
            ys = [b[3] for b in page.get_text('blocks') if top <= b[1] < bottom] + [r.y1 for img in page.get_images() for r in page.get_image_rects(img[0])]
            fill = (max(ys, default=top) - top) / (bottom - top)
            if fill < min_fill: out.append(f'Page {i + 1} is only {fill:.0%} full: something too big for the rest of the page moved to the next one')
    if leaks: out.append(f'{len(leaks)} place(s) show raw maths or code instead of text, e.g. ' + '; '.join(leaks[:4]))
    return out


def finish(out):
    try: WARNINGS.extend(w for w in pdf_checks(out) if w not in WARNINGS)
    except Exception as e: warn(f'The finished PDF could not be checked ({type(e).__name__})')
    print(json.dumps({'written': out, 'warnings': WARNINGS}))


def formula_lines(latex, avail, size=11, color='#1F1A2E', align='CENTER'):
    """A display formula as images, one per line (rows of align/aligned, or rows split by \\\\); maths the renderer cannot
    draw is shown as plain text instead of stopping the PDF."""
    out = []
    for line in TEX.lines(latex):
        try:
            fn, w, h, _ = math_img(line, size, True, color)
            if w > 2 * avail: warn('A formula had to be shrunk to under half its size to fit the page; it may be hard to read')
            if w > avail: h, w = h * avail / w, avail
            im = Image(fn, w, h); im.hAlign = align
            out += [im, Spacer(1, 2)]
        except Exception:
            out.append(Paragraph(html.escape(tex_text(line)), S['body']))
    return out


def as_math(s):
    """A symbol as the model wrote it ("rho", "$\\rho$", "\\rho", "V_1", "ρ") as text that draws: maths when it is maths."""
    s = str(s or '').strip()
    if '$' in s or not s: return s
    return f'${s}$' if re.search(r'[\\_^{}]', s) or re.fullmatch(r'[A-Za-z]{1,2}\d?', s) else s


DEFINED = set()          # symbols already explained in the current notes section: a "where" list does not repeat them
WHERE = ParagraphStyle('where', parent=S['cell'], fontSize=8.6, leading=11.5)


def where_list(rows, avail):
    """The symbols of a formula, one per row (symbol, then meaning and unit), as a compact list under it: no header, no
    grid, about two thirds of the width. A symbol already explained in the same section is left out."""
    key = lambda s: re.sub(r'[\s$\\{}]|mathrm|text', '', str(s))
    rows = [r for r in rows if r and key(r[0]) and key(r[0]) not in DEFINED]
    DEFINED.update(key(r[0]) for r in rows)
    if not rows: return []
    w1 = 52
    data = [[Paragraph(rich(as_math(r[0]), 9.4), WHERE),
             Paragraph(rich(str(r[1]) if len(r) > 1 else '', 9.4) + (f'<font color="#6B6480">, {rich(str(r[2]), 9.4)}</font>' if len(r) > 2 and not blank(r[2]) else ''), WHERE)]
            for r in rows]
    t = Table(data, colWidths=[w1, min(avail * 0.72, avail - 30) - w1])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -2), 0.3, LINE),
                           ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5), ('LEFTPADDING', (0, 0), (-1, -1), 4)]))
    t.hAlign = 'LEFT'                       # under the text, where the old "Here f is ..." lines were
    return [Spacer(1, 3), keep(Paragraph('<font color="#6B6480"><i>where</i></font>', WHERE)), t]


def formula(b, avail):
    """A display formula; a key formula (one of the 1-3 a student must remember) is larger, darker and framed."""
    if b.get('key'):
        inner = formula_lines(b['latex'], avail - 40, 12.5, '#2B1660')
        widest = max((i.drawWidth for i in inner if isinstance(i, Image)), default=avail)
        framed = Box(inner, bg=colors.HexColor('#F7F5FC'), bar=None, pad=7, width=min(avail, widest + 60), border=PURPLE)
        framed.hAlign = 'CENTER'
        out = [Spacer(1, 4), framed]
    else: out = [Spacer(1, 3)] + formula_lines(b['latex'], avail)
    return out + where_list(b.get('where') or [], avail) + [Spacer(1, 4)]


def indent(flow, width, left=14):
    t = Table([[flow]], colWidths=[width]); t.hAlign = 'LEFT'
    t.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), left), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                           ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
    return t


def steps(items, avail):
    """Numbered solution steps: "Step k · what is found", an optional sentence, the working as display maths (left, indented),
    the step's result, and any table or figure it needs."""
    out = []
    for k, s in enumerate(items, 1):
        if isinstance(s, str): s = {'text': s}
        if not isinstance(s, dict): continue
        out.append(keep(Paragraph(f'<font name="HeadM" color="#4D2A87">Step {k}</font>' + (f'  {rich(s["say"])}' if not blank(s.get('say')) else ''), S['body'])))
        if not blank(s.get('text')): out.append(P(s['text']))
        if not blank(s.get('latex')): out += [indent(f, avail) for f in formula_lines(s['latex'], avail - 20, 10.5, align='LEFT') if not isinstance(f, Spacer)]
        if not blank(s.get('result')): out.append(Paragraph('⇒ <b>' + rich(s['result']) + '</b>', ParagraphStyle('res', parent=S['body'], leftIndent=14)))
        out += blocks(s.get('blocks') or [], avail) + [Spacer(1, 4)]
    return out


def answer_bar(text, avail):
    t = Table([[Paragraph('<font name="Head" color="#4D2A87">Answer</font>  ' + rich(text), S['body'])]], colWidths=[avail])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white), ('LINEBEFORE', (0, 0), (0, -1), 3, PURPLE),
                           ('LEFTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    return t


def given_line(b):
    """"Given: m = 20 kg; V₁ = 5 m/s ..." and "To find: ...", from [symbol, value] pairs or "m = 20 kg" strings."""
    items = [f'{as_math(g[0])} = {g[1]}' if isinstance(g, (list, tuple)) and len(g) > 1 else str(g[0] if isinstance(g, (list, tuple)) else g)
             for g in (b.get('given') or []) if g]
    out = [P('**Given:** ' + '; '.join(items))] if items else []
    return out + ([P('**To find:** ' + b['find'])] if not blank(b.get('find')) else [])


def example(b, avail):
    title = re.sub(r'^((worked )?example\s*[:\-–—]*\s*)+', '', b.get('title') or '', flags=re.I)     # the label is added here, so a title must not repeat it
    inner = [keep(Paragraph(f'<font name="Head" color="#4D2A87">Worked example{": " + html.escape(title) if title else ""}</font>', S['body']))]
    inner += text_or_blocks(b.get('problem'), avail - 22) + given_line(b)
    inner.append(keep(Paragraph('<font name="HeadM" color="#4D2A87">Solution</font>', S['body'])))
    inner += steps(b['steps'], avail - 22) if b.get('steps') else text_or_blocks(b.get('solution'), avail - 22)
    if not blank(b.get('answer')): inner += [Spacer(1, 3), answer_bar(b['answer'], avail - 22)]
    if not blank(b.get('rushed')):
        inner += [Spacer(1, 5), Box([keep(Paragraph('Why the rushed answer is wrong', S['boxtitle'])), P(b['rushed'])], bg=colors.white, bar=PURPLE, width=avail - 22)]
    return [box(inner, width=avail), Spacer(1, 8)]


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
    elif t == 'formula': out += formula(b, avail)
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
        title = figure_number() + (' · ' if b.get('title') and FIGURES['section'] else '') + (b.get('title') or '')
        grp = ([Paragraph(rich(title), S['figtitle'])] if title else []) + \
              [image(fp, avail, width=wd, maxh=b.get('max_height_mm', 115) * mm)] + ([P(b['caption'], 'small')] if b.get('caption') else [])
        for f in grp[:-1]: keep(f)      # inside a box, box() glues these to the next flowable (a KeepTogether cannot sit in a table cell)
        out += ([KeepTogether(grp)] if len(grp) > 1 and avail >= TW else grp) + [Spacer(1, 4)]
    elif t == 'example': out += example(b, avail)
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

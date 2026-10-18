"""Previous-year questions: read the user's sources (web links, PDF or Word files) and verify what the model extracts.

The model never invents a PYQ: a question is kept only if its text appears in one of the sources."""
import html, io, ipaddress, re, socket, unicodedata, zipfile
from urllib.parse import urljoin, urlparse
import pymupdf
import requests
from bs4 import BeautifulSoup

MAX_BYTES, TIMEOUT, MAX_REDIRECTS = 20_000_000, 15, 3


def _check_url(url):
    """http(s) only, and never an address inside our own network (loopback, private, link-local, reserved)."""
    u = urlparse(url)
    if u.scheme not in ('http', 'https') or not u.hostname: raise ValueError(f'not a web address: {url}')
    for info in socket.getaddrinfo(u.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or not ip.is_global:
            raise ValueError(f'address not allowed: {url}')


def fetch_text(url):
    """Plain text of an HTML, PDF or text page (at most MAX_BYTES). Redirects are followed manually and re-checked."""
    for _ in range(MAX_REDIRECTS + 1):
        _check_url(url)
        r = requests.get(url, timeout=TIMEOUT, stream=True, allow_redirects=False, headers={'User-Agent': 'Mozilla/5.0 (Edwisely PDF builder)'})
        if r.is_redirect: url = urljoin(url, r.headers.get('location', '')); continue
        with r:
            r.raise_for_status()
            data = r.raw.read(MAX_BYTES + 1, decode_content=True)
        kind = r.headers.get('content-type', '').lower()
        if data[:5] == b'%PDF-' or 'pdf' in kind:      # file hosts often send PDFs as application/octet-stream
            if len(data) > MAX_BYTES: raise ValueError(f'the PDF is larger than {MAX_BYTES // 1_000_000} MB: {url}')
            return pdf_text(data)
        if 'html' in kind: return BeautifulSoup(data[:MAX_BYTES], 'html.parser').get_text('\n').replace('\x00', '')
        if 'text' in kind: return data[:MAX_BYTES].decode('utf-8', 'replace').replace('\x00', '')
        raise ValueError(f'unsupported content type {kind!r}: {url}')
    raise ValueError(f'too many redirects: {url}')


def pdf_text(data):
    doc = pymupdf.open(stream=data, filetype='pdf')
    if doc.needs_pass: raise ValueError('the PDF is password-protected')
    text = '\n'.join(p.get_text() for p in doc).replace('\x00', '')
    if len(text.strip()) < 20: raise ValueError('the PDF has no text layer (a scan); only digital PDFs can be read')
    return text


def file_text(name, data):
    """Plain text of an uploaded PDF or Word (.docx) file."""
    if name.lower().endswith('.pdf'): return pdf_text(data)
    xml = zipfile.ZipFile(io.BytesIO(data)).read('word/document.xml').decode('utf-8')
    xml = re.sub(r'<w:del\b.*?</w:del>|<w:instrText\b.*?</w:instrText>', '', xml, flags=re.S)     # tracked deletions, field codes
    xml = re.sub(r'<w:tab\b[^>]*/>', ' ', re.sub(r'<w:br\b[^>]*/>|<w:cr\b[^>]*/>|</w:p>', '\n', xml))
    return html.unescape(re.sub(r'<[^>]+>', '', xml)).replace('\x00', '')


SYMBOLS = {'≤': 'le', '≥': 'ge', '≠': 'ne', '×': 'times', '÷': 'div', '±': 'pm', '∞': 'infty', '→': 'to', '√': 'sqrt', '∑': 'sum', '∫': 'int'}


def _norm(s):
    """The text as letters and digits only, so the model's copy and the source match: ligatures (ﬁ), superscripts (x²) and
    full-width digits through NFKC; Greek letters and symbols as their LaTeX names (θ = \\theta, ≤ = \\le); LaTeX markup removed."""
    s = unicodedata.normalize('NFKC', str(s))
    s = ''.join(SYMBOLS.get(ch) or (unicodedata.name(ch, '').split()[-1].lower() if 'GREEK' in unicodedata.name(ch, '') else ch) for ch in s)
    s = re.sub(r'\\(?:left|right|mathrm|text|mathbf|frac|dfrac|tfrac|cdot)\b', '', s)
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def keep_verified(questions, texts):
    """Questions whose stem appears in one of the fetched page texts, with an answer and a source tag. Returns (kept, dropped reasons)."""
    pages = [_norm(t) for t in texts]
    kept, dropped = [], []
    for q in questions:
        stem = _norm(q.get('question', ''))[:120]
        if len(stem) < 30 or not any(stem in p for p in pages): dropped.append('not found in the source page: ' + str(q.get('question', ''))[:60])
        elif not q.get('answer'): dropped.append('no answer on the page: ' + str(q.get('question', ''))[:60])
        elif not q.get('source'): dropped.append('no paper/year on the page: ' + str(q.get('question', ''))[:60])
        else: kept.append(q)
    return kept, dropped

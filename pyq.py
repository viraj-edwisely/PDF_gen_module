"""Previous-year questions: read the user's sources (web links, PDF or Word files) and verify what the model extracts.

The model never invents a PYQ: a question is kept only if its text appears in one of the sources."""
import html, io, ipaddress, re, socket, zipfile
from urllib.parse import urljoin, urlparse
import pymupdf
import requests
from bs4 import BeautifulSoup

MAX_BYTES, TIMEOUT, MAX_REDIRECTS = 2_000_000, 15, 3


def _check_url(url):
    """http(s) only, and never an address inside our own network (loopback, private, link-local, reserved)."""
    u = urlparse(url)
    if u.scheme not in ('http', 'https') or not u.hostname: raise ValueError(f'not a web address: {url}')
    for info in socket.getaddrinfo(u.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f'address not allowed: {url}')


def fetch_text(url):
    """Plain text of an HTML, PDF or text page (at most MAX_BYTES). Redirects are followed manually and re-checked."""
    for _ in range(MAX_REDIRECTS + 1):
        _check_url(url)
        r = requests.get(url, timeout=TIMEOUT, stream=True, allow_redirects=False, headers={'User-Agent': 'Mozilla/5.0 (Edwisely PDF builder)'})
        if r.is_redirect: url = urljoin(url, r.headers.get('location', '')); continue
        r.raise_for_status()
        data = r.raw.read(MAX_BYTES, decode_content=True)
        kind = r.headers.get('content-type', '').lower()
        if 'pdf' in kind: return '\n'.join(p.get_text() for p in pymupdf.open(stream=data, filetype='pdf'))
        if 'html' in kind: return BeautifulSoup(data, 'html.parser').get_text('\n')
        if 'text' in kind: return data.decode('utf-8', 'replace')
        raise ValueError(f'unsupported content type {kind!r}: {url}')
    raise ValueError(f'too many redirects: {url}')


def file_text(name, data):
    """Plain text of an uploaded PDF or Word (.docx) file."""
    if name.lower().endswith('.pdf'): return '\n'.join(p.get_text() for p in pymupdf.open(stream=data, filetype='pdf'))
    xml = zipfile.ZipFile(io.BytesIO(data)).read('word/document.xml').decode('utf-8')
    xml = re.sub(r'<w:tab/>', ' ', re.sub(r'<w:br/>|</w:p>', '\n', xml))
    return html.unescape(re.sub(r'<[^>]+>', '', xml))


def _norm(s): return re.sub(r'[^a-z0-9]+', '', str(s).lower())


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

"""Previous-year questions: fetch the user's source pages, read the optional PYQ workbook, and verify what the model extracts.

The model never invents a PYQ: a question is kept only if its text appears in the fetched page (or comes from the workbook)."""
import ipaddress, re, socket
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


def workbook_questions(file, subject, topic, limit=12):
    """Candidate PYQs from the gate-pyq-extractor workbook (an uploaded .xlsx), ranked by how many topic words they contain."""
    import openpyxl
    ws = openpyxl.load_workbook(file, read_only=True)[subject[:31]]
    rows = list(ws.iter_rows(values_only=True)); col = {h: i for i, h in enumerate(rows[0])}
    words = [w for w in re.findall(r'[a-z]{4,}', topic.lower())]
    out = []
    for r in rows[1:]:
        opts = [r[col[f'Option{k}']] for k in range(1, 5)]
        q = (r[col['Question']] or '').replace('\\\\', '\\')
        hits = sum(len(re.findall(w, (q + ' ' + ' '.join(str(o or '') for o in opts)).lower())) for w in words)
        if not hits: continue
        numeric = r[col['field_type']] == 'Numerical'
        ans = r[col['Answer']]
        if numeric: ans = f"{r[col['Option1']]} to {r[col['Option2']]}" if r[col['Option1']] is not None else None
        elif ans: ans = ', '.join('ABCD'[int(x) - 1] for x in str(ans).split(','))
        out.append({'source': r[col['Source']], 'qtype': 'NAT' if numeric else r[col['field_type']], 'marks': 1 if r[col['Difficulty_level']] == 1 else 2,
                    'question': re.sub(r'\n\[Figure[^\]]*\]', '', q), 'options': None if numeric else [o for o in opts if o], 'answer': ans, 'hits': hits})
    return sorted([q for q in out if q['answer']], key=lambda q: -q['hits'])[:limit]

"""Book ingest: PDF -> page text, units, chunks with embeddings. Called from the Library page."""
import collections, re
import fitz
import db
from config import MAX_PAGES
from llm import embed

CHUNK_CHARS = 2400   # about 600 tokens
UNIT_LINE = re.compile(r'^\s*((?:unit|chapter|module|part)\s*[\dIVX]+\b.*?)[\s.\u2026·\-]*?(\d{1,4})\s*$', re.I)
HEADING = re.compile(r'^(\d+(\.\d+)*[.)]?\s+\S.{2,70}|[A-Z][A-Za-z0-9 ,:&\-()\']{2,70})$')


def extract_pages(doc):
    """(text per page, page offset). Paragraphs are separated by blank lines and headers/footers repeated on many pages
    are dropped. The offset is pdf_page - printed_page, voted from page numbers standing alone at the top or bottom."""
    raw = [[re.sub(r'-\n(?=[a-z])', '', b[4].replace('\x00', '')).replace('\n', ' ').strip() for b in p.get_text('blocks') if b[6] == 0] for p in doc]
    votes = collections.Counter(i - int(b) for i, blocks in enumerate(raw, 1) for b in blocks[:1] + blocks[-1:] if b.isdigit() and int(b) < i + 50)
    offset = votes.most_common(1)[0][0] if votes and votes.most_common(1)[0][1] >= 5 else 0
    seen = collections.Counter(k for blocks in raw for k in {re.sub(r'\d+', '#', b) for b in blocks if len(b) < 100})
    common = {k for k, n in seen.items() if n > max(3, 0.3 * len(raw))}
    return ['\n\n'.join(b for b in blocks if b and not (len(b) < 100 and re.sub(r'\d+', '#', b) in common)) for blocks in raw], offset


def detect_units(doc, pages, offset):
    """Units as (name, first printed page, last printed page): PDF bookmarks, else the printed contents pages, else none."""
    found = [(t.strip(), p - offset) for lvl, t, p in doc.get_toc() if lvl == 1 and p > 0]
    if len(found) < 2:
        found = []
        for t in pages[:30]:
            for line in t.replace('\n\n', '\n').split('\n'):
                m = UNIT_LINE.match(line)
                if m: found.append((re.sub(r'[\s.\u2026]+$', '', m.group(1)), int(m.group(2))))
    if len(found) < 2: return []
    last = len(pages) - offset
    return [(n, s, (found[i + 1][1] - 1 if i + 1 < len(found) else last)) for i, (n, s) in enumerate(found)]


def chunk_pages(pages):
    """Chunks of about CHUNK_CHARS built from paragraphs; each keeps its PDF page range and nearest heading."""
    chunks, cur, size, heading = [], [], 0, ''          # cur: [(paragraph, pdf page, heading)]
    def close(): chunks.append((cur[0][1], cur[-1][1], cur[0][2], '\n\n'.join(p for p, _, _ in cur)))
    for n, text in enumerate(pages, 1):
        for para in (p for p in text.split('\n\n') if p.strip()):
            if HEADING.match(para) and not para.endswith('.'): heading = para
            if cur and size + len(para) > CHUNK_CHARS:
                close()
                cur = cur[-1:] if len(cur[-1][0]) < CHUNK_CHARS // 3 else []     # one short paragraph of overlap
                size = sum(len(p) for p, _, _ in cur)
            cur.append((para, n, heading)); size += len(para)
    if cur: close()
    return chunks


def vec(v): return '[' + ','.join(f'{x:.6f}' for x in v) + ']'


def ingest(book_id, pdf_bytes, progress=lambda f, msg: None):
    """Fill pages, units and chunks for a book. Sets books.status to ready or failed."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        if len(doc) > MAX_PAGES: raise ValueError(f'{len(doc)} pages; the limit is {MAX_PAGES}')
        progress(0.05, 'Reading pages')
        pages, offset = extract_pages(doc)
        if sum(len(t) < 20 for t in pages) > len(pages) / 2: raise ValueError('this PDF looks scanned (little extractable text); scanned books are not supported yet')
        db.sql('delete from pages where book_id=%s', (book_id,)); db.sql('delete from units where book_id=%s', (book_id,)); db.sql('delete from chunks where book_id=%s', (book_id,))
        db.many('insert into pages (book_id, pdf_page, text) values (%s,%s,%s)', [(book_id, i, t) for i, t in enumerate(pages, 1)])
        db.many('insert into units (book_id, name, start_page, end_page) values (%s,%s,%s,%s)', [(book_id, *u) for u in detect_units(doc, pages, offset)])
        progress(0.2, 'Splitting into chunks')
        chunks = chunk_pages(pages)
        for i in range(0, len(chunks), 100):
            batch = chunks[i:i + 100]
            progress(0.2 + 0.75 * i / len(chunks), f'Embedding chunks {i + 1}-{i + len(batch)} of {len(chunks)}')
            db.many('insert into chunks (book_id, page_start, page_end, heading, text, embedding) values (%s,%s,%s,%s,%s,%s::vector)',
                    [(book_id, a, b, h, t, vec(v)) for (a, b, h, t), v in zip(batch, embed([c[3] for c in batch]))])
        db.sql("update books set status='ready', error=null, page_count=%s, page_offset=%s where id=%s", (len(pages), offset, book_id))
        progress(1.0, 'Ready')
    except Exception as e:
        db.sql("update books set status='failed', error=%s where id=%s", (str(e)[:500], book_id))
        raise

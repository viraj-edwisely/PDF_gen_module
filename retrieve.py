"""Retrieval: turn a book scope (printed page range) and a topic into the book text the model sees."""
import db
from config import SCOPE_TOKEN_BUDGET, TOPIC_TOKEN_BUDGET
from ingest import vec
from llm import embed

FOUND_SIM = 0.30   # best cosine similarity below this: the topic is not in this scope


def topic_context(book, start, end, topic):
    """book: a books row; start/end: printed pages. Returns {'text', 'found', 'whole_scope'}.
    A small scope is sent whole in page order; a larger one is searched (vector + keyword, fused) down to a budget."""
    if not book: return {'text': '', 'found': False, 'whole_scope': False}      # runs without a book
    off, bid = book['page_offset'], book['id']
    a, b = start + off, end + off
    scope = 'book_id=%s and page_start between %s and %s'
    near = db.sql(f'select page_start, 1 - (embedding <=> %s::vector) as sim from chunks where {scope} order by embedding <=> %s::vector limit 30',
                  (qv := vec(embed([topic])[0]), bid, a, b, qv))
    found = bool(near) and near[0]['sim'] >= FOUND_SIM
    size = db.sql('select coalesce(sum(length(text)), 0) n from pages where book_id=%s and pdf_page between %s and %s', (bid, a, b))[0]['n']
    if size / 4 <= SCOPE_TOKEN_BUDGET:
        rows = db.sql('select pdf_page, text from pages where book_id=%s and pdf_page between %s and %s order by pdf_page', (bid, a, b))
        return {'text': '\n\n'.join(f"[p. {r['pdf_page'] - off}]\n{r['text']}" for r in rows), 'found': found, 'whole_scope': True}
    by_vec = [r['id'] for r in db.sql(f'select id from chunks where {scope} order by embedding <=> %s::vector limit 30', (bid, a, b, qv))]
    by_word = [r['id'] for r in db.sql(f"select id from chunks where {scope} and tsv @@ websearch_to_tsquery('english', %s) "
                                       "order by ts_rank_cd(tsv, websearch_to_tsquery('english', %s)) desc limit 30", (bid, a, b, topic, topic))]
    score = {}
    for ranked in (by_vec, by_word):
        for rank, cid in enumerate(ranked): score[cid] = score.get(cid, 0) + 1 / (60 + rank)    # reciprocal rank fusion
    chosen, used = [], 0
    for cid in sorted(score, key=score.get, reverse=True):
        row = db.sql('select id, page_start, page_end, heading, text from chunks where id=%s', (cid,))[0]
        if used + len(row['text']) > TOPIC_TOKEN_BUDGET * 4: continue
        chosen.append(row); used += len(row['text'])
    chosen.sort(key=lambda r: r['page_start'])
    return {'text': '\n\n'.join(f"[p. {r['page_start'] - off}-{r['page_end'] - off}] {r['heading']}\n{r['text']}" for r in chosen), 'found': found, 'whole_scope': False}

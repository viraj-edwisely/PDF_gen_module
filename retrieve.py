"""Retrieval: turn a book scope (printed page range) and a topic into the book text the model sees."""
from itertools import zip_longest
import db
from config import SCOPE_TOKEN_BUDGET, TOPIC_TOKEN_BUDGET
from ingest import vec
from llm import embed

FOUND_SIM = 0.30   # best cosine similarity at or above this: the topic is in this scope
NEAR_SIM = 0.20    # chunks less similar than this to every search are never sent (between the two: the closest passages, flagged as loose)


def topic_context(book, start, end, topic, sections=()):
    """book: a books row; start/end: printed pages; sections: headings of planned sections, searched as well, so the
    text covers each section and not only what the topic name finds. Returns {'text', 'found', 'whole_scope'}.
    A small scope is sent whole in page order; a larger one is searched (vector + keyword per search, fused) down to a budget."""
    if not book: return {'text': '', 'found': False, 'whole_scope': False}      # runs without a book
    off, bid = book['page_offset'], book['id']
    a, b = start + off, end + off
    scope = 'book_id=%s and page_start between %s and %s'
    queries = [topic, *sections]
    ranked, best = [], 0
    for q, qv in zip(queries, map(vec, embed(queries))):
        near = db.sql(f'select id, 1 - (embedding <=> %s::vector) as sim from chunks where {scope} order by embedding <=> %s::vector limit 30', (qv, bid, a, b, qv))
        words = db.sql(f"select id, 1 - (embedding <=> %s::vector) as sim from chunks where {scope} and tsv @@ websearch_to_tsquery('english', %s) "
                       "order by ts_rank_cd(tsv, websearch_to_tsquery('english', %s)) desc limit 30", (qv, bid, a, b, q, q))
        best = max([best] + [r['sim'] for r in near])
        score = {}
        for hits in (near, words):
            for rank, r in enumerate(hits):
                if r['sim'] >= NEAR_SIM: score[r['id']] = score.get(r['id'], 0) + 1 / (60 + rank)    # reciprocal rank fusion
        ranked.append(sorted(score, key=score.get, reverse=True))
    size = db.sql('select coalesce(sum(length(text)), 0) n from pages where book_id=%s and pdf_page between %s and %s', (bid, a, b))[0]['n']
    out = {'text': '', 'found': best >= FOUND_SIM, 'whole_scope': size / 4 <= SCOPE_TOKEN_BUDGET}
    if best < NEAR_SIM: return out                                                # nothing in the scope is about this topic
    if out['whole_scope']:
        rows = db.sql('select pdf_page, text from pages where book_id=%s and pdf_page between %s and %s order by pdf_page', (bid, a, b))
        return {**out, 'text': '\n\n'.join(f"[p. {r['pdf_page'] - off}]\n{r['text']}" for r in rows)}
    top = list(dict.fromkeys(c for tier in zip_longest(*ranked) for c in tier if c is not None))[:60]   # each search's best in turn
    rows = {r['id']: r for r in db.sql('select id, page_start, page_end, heading, text from chunks where id = any(%s)', (top,))}
    chosen, used = [], 0
    for cid in top:
        if used + len(rows[cid]['text']) > TOPIC_TOKEN_BUDGET * 4: continue
        chosen.append(rows[cid]); used += len(rows[cid]['text'])
    chosen.sort(key=lambda r: r['page_start'])
    return {**out, 'text': '\n\n'.join(f"[p. {r['page_start'] - off}-{r['page_end'] - off}] {r['heading']}\n{r['text']}" for r in chosen)}

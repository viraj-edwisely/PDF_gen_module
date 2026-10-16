"""Generate page: choose the type of PDF, the book, the scope and the topics, then start a run."""
import io
import streamlit as st
import db, jobs, pyq
from config import COST_CAP, MAX_TOPICS, MAX_URLS, PROVIDERS, SCOPE_TOKEN_BUDGET, TOPIC_TOKEN_BUDGET, cost, secret
from ui import user

st.title('Generate PDFs')
mode = 'gate' if st.radio('Type of PDF', ['GATE', 'Non-GATE'], horizontal=True, help='GATE: the Edwisely GATE topic guide with exam-style questions. Non-GATE: the learning-module style.') == 'GATE' else 'nongate'

books = db.sql("select * from books where status='ready' order by title")
if not books: st.info('Upload a book on the Library page first.'); st.stop()
book = st.selectbox('Book', books, format_func=lambda b: f"{b['title']} ({b['subject']})")

units = db.sql('select * from units where book_id=%s order by start_page', (book['id'],))
last = max(1, book['page_count'] - book['page_offset'])
how = st.radio('Scope', ['Unit', 'Page range'] if units else ['Page range'], horizontal=True)
if how == 'Unit':
    unit = st.selectbox('Unit', units, format_func=lambda u: f"{u['name']} (pages {u['start_page']}-{u['end_page']})")
    start, end = unit['start_page'], unit['end_page']
else:
    c1, c2 = st.columns(2)
    start = c1.number_input('First page (printed page number)', 1, last, 1)
    end = c2.number_input('Last page', 1, last, last)
topics = list(dict.fromkeys(t.strip() for t in st.text_area('Topics (one per line)', height=140, help='GATE: one PDF per topic. Non-GATE: one module PDF covering all of them.').splitlines() if t.strip()))

options = {'topics': topics}
if mode == 'gate':
    c1, c2 = st.columns(2)
    options['paper'] = c1.text_input('GATE paper code', value=book['paper'] or '').strip().upper()
    options['subject'] = c2.text_input('Subject', value=book['subject']).strip()
    options['syllabus_line'] = st.text_input('Syllabus line (optional; the model writes one if empty)').strip()
    options['urls'] = [u.strip() for u in st.text_area('Previous-year question sources: web page or PDF links, one per line (optional)', height=90).splitlines() if u.strip()]
    workbook = st.file_uploader('Or a PYQ workbook (.xlsx from the PYQ extractor, optional)', type='xlsx')
else:
    options['subject'] = st.text_input('Subject', value=book['subject']).strip()
    options['prompt'] = st.text_area('Your instructions (optional; empty uses the standard module template)', height=110).strip()
    c1, c2 = st.columns(2)
    options['study_time'], options['audience'] = c1.text_input('Study time (optional)').strip(), c2.text_input('Recommended for (optional)').strip()

ready = [p for p, c in PROVIDERS.items() if secret(c['key'])]
provider = st.selectbox('Writer', ready, help='The AI provider that writes the content.')

# cost estimate from the size of the scope
scope_tokens = db.sql('select coalesce(sum(length(text)), 0) / 4 n from pages where book_id=%s and pdf_page between %s and %s', (book['id'], start + book['page_offset'], end + book['page_offset']))[0]['n']
n = max(1, len(topics))
context = scope_tokens if scope_tokens <= SCOPE_TOKEN_BUDGET else TOPIC_TOKEN_BUDGET
calls, out_tokens = (4, 40_000) if mode == 'gate' else (2 + -(-n // 3), 9_000 * n + 12_000)    # GATE: plan, 2 notes, questions; Non-GATE: plan, topics in threes, end matter
estimate = cost(provider, calls * (context + 15_000), out_tokens) * (n if mode == 'gate' else 1)

errors = []
if not topics: errors.append('Enter at least one topic.')
if len(topics) > MAX_TOPICS: errors.append(f'At most {MAX_TOPICS} topics per run.')
if start > end: errors.append('The first page is after the last page.')
if mode == 'gate':
    if not options['paper']: errors.append('Enter the GATE paper code (for example CS).')
    if len(options['urls']) > MAX_URLS: errors.append(f'At most {MAX_URLS} source links.')
    if any(not u.startswith(('http://', 'https://')) for u in options['urls']): errors.append('Source links must start with http:// or https://')
if not options['subject']: errors.append('Enter the subject.')
st.caption(f'Estimated cost: about ${estimate:.2f}. A run stops by itself at ${COST_CAP:.0f}; finished PDFs are kept.')
for e in errors: st.error(e)

if st.button('Generate', type='primary', disabled=bool(errors)):
    if mode == 'gate' and workbook:
        try: options['workbook'] = {t: pyq.workbook_questions(io.BytesIO(workbook.getvalue()), options['subject'], t) for t in topics}
        except KeyError: st.error(f'The workbook has no sheet named "{options["subject"][:31]}".'); st.stop()
    run_id = jobs.create_run(mode, book['id'], (int(start), int(end)), provider, options, user())
    st.success(f'Run {run_id} started.')
    st.page_link('views/runs.py', label='Open the Runs page to follow it', icon='📄')

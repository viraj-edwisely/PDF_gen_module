"""Generate page: choose the type of PDF, the book, the scope and the topics, then start a run."""
import io
import streamlit as st
import db, jobs, pyq
from config import COST_CAP, MAX_TOPICS, MAX_URLS, PROVIDERS, SCOPE_TOKEN_BUDGET, TOPIC_TOKEN_BUDGET, cost, secret
from ui import user

st.title('Generate PDFs')
mode = 'gate' if st.radio('Type of PDF', ['GATE', 'Non-GATE'], horizontal=True, help='GATE: the Edwisely GATE topic guide with exam-style questions. Non-GATE: the learning-module style.') == 'GATE' else 'nongate'

books = db.sql("select * from books where status='ready' order by title")
book = st.selectbox('Book (optional)', [None] + books, format_func=lambda b: 'No book: the writer uses its own knowledge' if b is None else f"{b['title']} ({b['subject']})",
                    help='With a book, the content follows it. Without one, the writer works from the topic names alone.')

start = end = None
if book:
    units = db.sql('select * from units where book_id=%s order by start_page', (book['id'],))
    last = max(1, book['page_count'] - book['page_offset'])
    how = st.radio('Scope', ['Unit', 'Page range'] if units else ['Page range'], horizontal=True)
    if not units: st.caption('No units were found for this book. To pick a unit here instead, add them to the book on the Library page.')
    if how == 'Unit':
        unit = st.selectbox('Unit', units, format_func=lambda u: f"{u['name']} (pages {u['start_page']}-{u['end_page']})")
        start, end = unit['start_page'], unit['end_page']
    else:
        c1, c2 = st.columns(2)
        start = c1.number_input('First page (printed page number)', 1, last, 1)
        end = c2.number_input('Last page', 1, last, last)
default = book or {'paper': '', 'subject': ''}

# topics: one input box each (GATE: each also takes its own PYQ sheet)
st.subheader('Topics')
st.caption('GATE: one PDF per topic. Non-GATE: one module PDF covering all of them.')
ids = st.session_state.setdefault('topic_ids', [0])
def add_topic(): st.session_state.topic_ids.append(max(st.session_state.topic_ids) + 1)
def remove_topic(i): st.session_state.topic_ids.remove(i)
names, sheets = [], {}
for k, i in enumerate(ids, 1):
    with st.container(border=True):
        name = st.text_input(f'Topic {k}', key=f'topic{i}').strip()
        sheet = st.file_uploader('PYQ sheet for this topic (optional, .xlsx)', type='xlsx', key=f'sheet{i}') if mode == 'gate' else None
        if len(ids) > 1: st.button('Remove this topic', key=f'remove{i}', on_click=remove_topic, args=(i,))
    if name and name not in names: names.append(name)
    if name and sheet and name not in sheets: sheets[name] = sheet
topics = names
st.button('＋ Add a topic', on_click=add_topic, disabled=len(ids) >= MAX_TOPICS)

options = {'topics': topics}
if mode == 'gate':
    c1, c2 = st.columns(2)
    options['paper'] = c1.text_input('GATE paper code', value=default['paper'] or '').strip().upper()
    options['subject'] = c2.text_input('Subject', value=default['subject']).strip()
    options['syllabus_line'] = st.text_input('Syllabus line (optional; the model writes one if empty)').strip()
    options['urls'] = [u.strip() for u in st.text_area('Previous-year question sources: web page or PDF links, one per line (optional)', height=90).splitlines() if u.strip()]
else:
    options['subject'] = st.text_input('Subject', value=default['subject']).strip()
    options['prompt'] = st.text_area('Your instructions (optional; empty uses the standard module template)', height=110).strip()
    c1, c2 = st.columns(2)
    options['study_time'], options['audience'] = c1.text_input('Study time (optional)').strip(), c2.text_input('Recommended for (optional)').strip()

ready = [p for p, c in PROVIDERS.items() if secret(c['key'])]
provider = st.selectbox('Writer', ready, help='The AI provider that writes the content.')

# cost estimate from the size of the scope
scope_tokens = db.sql('select coalesce(sum(length(text)), 0) / 4 n from pages where book_id=%s and pdf_page between %s and %s', (book['id'], start + book['page_offset'], end + book['page_offset']))[0]['n'] if book else 0
n = max(1, len(topics))
context = scope_tokens if scope_tokens <= SCOPE_TOKEN_BUDGET else TOPIC_TOKEN_BUDGET
calls, out_tokens = (4, 40_000) if mode == 'gate' else (2 + -(-n // 3), 9_000 * n + 12_000)    # GATE: plan, 2 notes, questions; Non-GATE: plan, topics in threes, end matter
estimate = cost(provider, calls * (context + 15_000), out_tokens) * (n if mode == 'gate' else 1)

errors = []
if not topics: errors.append('Enter at least one topic.')
if len(topics) > MAX_TOPICS: errors.append(f'At most {MAX_TOPICS} topics per run.')
if book and start > end: errors.append('The first page is after the last page.')
if mode == 'gate':
    if not options['paper']: errors.append('Enter the GATE paper code (for example CS).')
    if len(options['urls']) > MAX_URLS: errors.append(f'At most {MAX_URLS} source links.')
    if any(not u.startswith(('http://', 'https://')) for u in options['urls']): errors.append('Source links must start with http:// or https://')
if not options['subject']: errors.append('Enter the subject.')
st.caption(f'Estimated cost: about ${estimate:.2f}. A run stops by itself at ${COST_CAP:.0f}; finished PDFs are kept.')
for e in errors: st.error(e)

if st.button('Generate', type='primary', disabled=bool(errors)):
    if mode == 'gate' and sheets:
        try: options['workbook'] = {t: pyq.workbook_questions(io.BytesIO(f.getvalue()), options['subject'], t) for t, f in sheets.items()}
        except KeyError as e: st.error(f'A PYQ sheet could not be read: {e}. It needs a sheet named "{options["subject"][:31]}" with the columns Question, Option1-4, Answer, field_type, Difficulty_level and Source.'); st.stop()
    run_id = jobs.create_run(mode, book['id'] if book else None, (start and int(start), end and int(end)), provider, options, user())
    st.success(f'Run {run_id} started.')
    st.page_link('views/runs.py', label='Open the Runs page to follow it', icon='📄')

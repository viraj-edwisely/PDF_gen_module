"""Generate page: what to make, from which book, which topics, the details; then review and start the run."""
import io
import streamlit as st
import db, jobs, llm, pyq
from config import COST_CAP, MAX_TOPICS, MAX_URLS, PROVIDERS, SCOPE_TOKEN_BUDGET, TOPIC_PARALLEL, TOPIC_TOKEN_BUDGET, VERIFY_PROVIDER, cost, secret
from ui import user

st.title('Generate PDFs')

# 1. what to make
st.subheader('1 · What to make')
c1, c2 = st.columns([3, 2])
mode = 'gate' if c1.radio('Type of PDF', ['GATE', 'Non-GATE'], horizontal=True,
                          help='GATE: one Edwisely GATE topic guide per topic, with exam-style questions. Non-GATE: one learning module covering all topics.') == 'GATE' else 'nongate'
ready = [p for p, c in PROVIDERS.items() if secret(c['key'])]
provider = c2.selectbox('Writer', ready, format_func=lambda p: f"{p} ({PROVIDERS[p]['model']})", help='The AI model that writes the content.')
if c2.button('Check that this writer works', help='Sends one tiny request (costs a fraction of a cent) to confirm the key and the model name.'):
    with st.spinner('Asking the writer...'): err = llm.ping(provider)
    (c2.error(err) if err else c2.success('The writer answered.'))

# 2. source
st.subheader('2 · Source')
books = db.sql("select * from books where status='ready' order by title")
book = st.selectbox('Book (optional)', [None] + books, format_func=lambda b: 'No book: the writer uses its own knowledge' if b is None else f"{b['title']} ({b['subject']})",
                    help='With a book, the content follows it. Without one, the writer works from the topic names alone. Upload books on the Library page.')
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

# 3. topics: one row each (GATE: each also takes its own PYQ sheet)
st.subheader('3 · Topics')
st.caption('GATE: one PDF per topic. Non-GATE: one module PDF covering all of them.')
ids = st.session_state.setdefault('topic_ids', [0])
def add_topic(): st.session_state.topic_ids.append(max(st.session_state.topic_ids) + 1)
def remove_topic(i): st.session_state.topic_ids.remove(i)
names, sheets = [], {}
for k, i in enumerate(ids, 1):
    cols = st.columns([5, 4, 1] if mode == 'gate' else [9, 1], vertical_alignment='bottom')
    name = cols[0].text_input(f'Topic {k}', key=f'topic{i}', placeholder='e.g. Addressing modes and effective address').strip()
    sheet = cols[1].file_uploader('PYQ sheet (optional, .xlsx)', type='xlsx', key=f'sheet{i}') if mode == 'gate' else None
    if len(ids) > 1: cols[-1].button('✕', key=f'remove{i}', on_click=remove_topic, args=(i,), help='Remove this topic')
    if name and name not in names: names.append(name)
    if name and sheet and name not in sheets: sheets[name] = sheet
topics = names
st.button('＋ Add a topic', on_click=add_topic, disabled=len(ids) >= MAX_TOPICS)

# 4. details
st.subheader('4 · Details')
options = {'topics': topics}
if mode == 'gate':
    c1, c2 = st.columns([1, 3])
    options['paper'] = c1.text_input('GATE paper code', value=default['paper'] or '', placeholder='CS').strip().upper()
    options['subject'] = c2.text_input('Subject', value=default['subject'], placeholder='e.g. Computer Organization and Architecture').strip()
    options['syllabus_line'] = st.text_input('Syllabus line (optional; the writer writes one if empty)').strip()
    with st.expander('Previous-year question sources (optional)'):
        options['urls'] = [u.strip() for u in st.text_area('Web pages or PDF links with GATE previous-year questions, one per line', height=90).splitlines() if u.strip()]
        st.caption('Questions are kept only if their exact text is found on the page. Attach a PYQ sheet per topic above for questions from your own bank '
                   '(sheet named like the subject, columns Question, Option1-4, Answer, field_type, Difficulty_level, Source).')
    has_verifier = bool(secret(PROVIDERS[VERIFY_PROVIDER]['key']))
    options['verify'] = st.toggle('Double-check answers with a second model', value=True,
                                  help=f"{VERIFY_PROVIDER if has_verifier else provider} re-solves every question and worked example; disputed items go back to the writer once. Adds about $0.05-0.10 per PDF.")
else:
    options['subject'] = st.text_input('Subject', value=default['subject']).strip()
    options['prompt'] = st.text_area('Your instructions (optional; empty uses the standard module template)', height=110).strip()
    c1, c2 = st.columns(2)
    options['study_time'], options['audience'] = c1.text_input('Study time (optional)').strip(), c2.text_input('Recommended for (optional)').strip()

# 5. review
st.subheader('5 · Review and start')
scope_tokens = db.sql('select coalesce(sum(length(text)), 0) / 4 n from pages where book_id=%s and pdf_page between %s and %s', (book['id'], start + book['page_offset'], end + book['page_offset']))[0]['n'] if book else 0
n = max(1, len(topics))
context = scope_tokens if scope_tokens <= SCOPE_TOKEN_BUDGET else TOPIC_TOKEN_BUDGET
calls, out_tokens = (4, 40_000) if mode == 'gate' else (2 + -(-n // 3), 9_000 * n + 12_000)    # GATE: plan, 2 notes, questions; Non-GATE: plan, topics in threes, end matter
estimate = 1.15 * cost(provider, calls * (context + 15_000), out_tokens) * (n if mode == 'gate' else 1)     # +15% for repairs
if mode == 'gate' and options.get('verify'):
    estimate += n * cost(VERIFY_PROVIDER if secret(PROVIDERS[VERIFY_PROVIDER]['key']) else provider, 20_000, 3_000)
minutes = (-(-n // TOPIC_PARALLEL) * 10) if mode == 'gate' else 12

errors = []
if not topics: errors.append('Enter at least one topic.')
if len(topics) > MAX_TOPICS: errors.append(f'At most {MAX_TOPICS} topics per run.')
if book and start > end: errors.append('The first page is after the last page.')
if mode == 'gate':
    if not options['paper']: errors.append('Enter the GATE paper code (for example CS).')
    if len(options['urls']) > MAX_URLS: errors.append(f'At most {MAX_URLS} source links.')
    if any(not u.startswith(('http://', 'https://')) for u in options['urls']): errors.append('Source links must start with http:// or https://')
if not options['subject']: errors.append('Enter the subject.')

with st.container(border=True):
    what = f"{len(topics)} GATE PDF{'s' if len(topics) != 1 else ''}" if mode == 'gate' else f"1 learning module with {len(topics)} topic{'s' if len(topics) != 1 else ''}"
    src = (book['title'] + (f', pages {start}-{end}' if start else '')) if book else "no book (the writer's own knowledge)"
    st.markdown(f"**{what}** · writer {provider} · source: {src}\n\n"
                f"Estimated cost **about ${estimate:.2f}**, time **about {minutes} minutes**. A run stops by itself at ${COST_CAP:.0f}; finished PDFs are kept.")
    if errors: st.info('Still needed: ' + ' '.join(errors))
    if st.button('Generate', type='primary', disabled=bool(errors)):
        if mode == 'gate' and sheets:
            try: options['workbook'] = {t: pyq.workbook_questions(io.BytesIO(f.getvalue()), options['subject'], t) for t, f in sheets.items()}
            except KeyError as e: st.error(f'A PYQ sheet could not be read: {e}. It needs a sheet named "{options["subject"][:31]}" with the columns Question, Option1-4, Answer, field_type, Difficulty_level and Source.'); st.stop()
        run_id = jobs.create_run(mode, book['id'] if book else None, (start and int(start), end and int(end)), provider, options, user())
        st.success(f'Run #{run_id} started.')
        st.page_link('views/runs.py', label='Open the Runs page to follow it', icon='📄')

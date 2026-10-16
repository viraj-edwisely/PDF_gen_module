"""Generate page: what to make, from which book, which topics, the details; then review and start the run."""
import io
import pandas as pd
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
if st.session_state.get('subject_book') != (book and book['id']):          # a newly chosen book fills in its subject and paper
    st.session_state.subject_book = book and book['id']
    for k in ('subject', 'paper'):
        if book or k not in st.session_state: st.session_state[k] = default[k] or ''

# 3. topics: one row each (GATE: each also takes its own PYQ source: PDF or Word files, or links)
st.subheader('3 · Topics')
st.caption('GATE: one PDF per topic. Non-GATE: one module PDF covering all of them.')
ids = st.session_state.setdefault('topic_ids', [0])
def add_topic(): st.session_state.topic_ids.append(max(st.session_state.topic_ids) + 1)
def remove_topic(i): st.session_state.topic_ids.remove(i)

def import_topics():
    """Fill the topic rows (and the subject) from the uploaded sheet: empty rows are replaced, filled ones kept."""
    s = st.session_state
    if not s.topics_file: return
    try:
        df = pd.read_excel(s.topics_file, dtype=str).rename(columns=lambda c: str(c).strip().lower())
        sheet = [t.strip() for t in df['topic'].dropna() if t.strip()]
    except Exception as e:
        s.import_msg = ('error', f'The sheet could not be read: it needs a column named Topic ({e}).'); return
    keep = [i for i in s.topic_ids if s.get(f'topic{i}', '').strip()]
    have = {s[f'topic{i}'].strip() for i in keep}
    new = [t for t in dict.fromkeys(sheet) if t not in have][:MAX_TOPICS - len(keep)]
    first = max(s.topic_ids) + 1
    for k, t in enumerate(new): s[f'topic{first + k}'] = t
    s.topic_ids = keep + list(range(first, first + len(new))) or [first]
    subjects = [x.strip() for x in df.get('subject', pd.Series(dtype=str)).dropna() if x.strip()]
    if subjects: s.subject = subjects[0]
    skipped = len(set(sheet)) - len(new)
    s.import_msg = ('success', f'Added {len(new)} topic(s) from the sheet' + (f'; {skipped} skipped (already listed, or more than {MAX_TOPICS} in all).' if skipped else '.'))

with st.expander('Import topics from an Excel sheet'):
    st.caption('One row per topic, with the columns **Subject** and **Topic** (Subject is optional; the first one fills in the Subject field below).')
    c1, c2 = st.columns([3, 1], vertical_alignment='bottom')
    c1.file_uploader('Topics sheet (.xlsx)', type='xlsx', key='topics_file', on_change=import_topics)
    template = io.BytesIO()
    pd.DataFrame({'Subject': ['Computer Organization and Architecture'] * 2, 'Topic': ['Addressing modes', 'Instruction formats']}).to_excel(template, index=False)
    c2.download_button('Download the template', template.getvalue(), 'topics_template.xlsx')
    if msg := st.session_state.pop('import_msg', None): getattr(st, msg[0])(msg[1])
names, sources = [], {}          # sources: topic -> ('PDF' | 'Word' | 'Links', files or links) with its previous-year questions
for k, i in enumerate(ids, 1):
    cols = st.columns([6, 3, 1] if mode == 'gate' else [9, 1], vertical_alignment='bottom')
    name = cols[0].text_input(f'Topic {k}', key=f'topic{i}', placeholder='e.g. Addressing modes and effective address').strip()
    kind = cols[1].segmented_control('PYQ source (optional)', ['PDF', 'Word', 'Links'], key=f'pyqkind{i}',
                                     help='Previous-year GATE questions for this topic. Only questions whose exact text is found in the source are used.') if mode == 'gate' else None
    if len(ids) > 1: cols[-1].button('✕', key=f'remove{i}', on_click=remove_topic, args=(i,), help='Remove this topic')
    got = []
    if kind == 'Links':
        got = [u.strip() for u in st.text_area(f'Links for topic {k} (web pages or PDFs, one per line)', key=f'pyqurls{i}', height=68).splitlines() if u.strip()]
    elif kind:
        got = st.file_uploader(f'{kind} file(s) for topic {k}', type='pdf' if kind == 'PDF' else 'docx', accept_multiple_files=True, key=f'pyqfile{i}')
    if name and name not in names: names.append(name)
    if name and got: sources.setdefault(name, (kind, got))
topics = names
st.button('＋ Add a topic', on_click=add_topic, disabled=len(ids) >= MAX_TOPICS)

# 4. details
st.subheader('4 · Details')
options = {'topics': topics}
if mode == 'gate':
    c1, c2 = st.columns([1, 3])
    options['paper'] = c1.text_input('GATE paper code', key='paper', placeholder='CS').strip().upper()
    options['subject'] = c2.text_input('Subject', key='subject', placeholder='e.g. Computer Organization and Architecture').strip()
    options['syllabus_line'] = st.text_input('Syllabus line (optional; the writer writes one if empty)').strip()
    has_verifier = bool(secret(PROVIDERS[VERIFY_PROVIDER]['key']))
    options['verify'] = st.toggle('Double-check answers with a second model', value=True,
                                  help=f"{VERIFY_PROVIDER if has_verifier else provider} re-solves every question and worked example; disputed items go back to the writer once. Adds about $0.05-0.10 per PDF.")
else:
    options['subject'] = st.text_input('Subject', key='subject').strip()
    c1, c2 = st.columns(2)
    options['study_time'], options['audience'] = c1.text_input('Study time (optional)').strip(), c2.text_input('Recommended for (optional)').strip()
options['prompt'] = st.text_area('User prompt (optional)', height=100, placeholder='e.g. Focus on numerical problems on effective address calculation; use the notation of Hamacher.',
                                 help='Extra instructions sent to the writer with every step. GATE: the GATE format stays the same. '
                                      'Non-GATE: overrides the standard module template where they conflict.').strip()

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
    if any(len(got) > MAX_URLS for _, got in sources.values()): errors.append(f'At most {MAX_URLS} PYQ links or files per topic.')
    if any(kind == 'Links' and not u.startswith(('http://', 'https://')) for kind, got in sources.values() for u in got): errors.append('PYQ links must start with http:// or https://')
if not options['subject']: errors.append('Enter the subject.')

with st.container(border=True):
    what = f"{len(topics)} GATE PDF{'s' if len(topics) != 1 else ''}" if mode == 'gate' else f"1 learning module with {len(topics)} topic{'s' if len(topics) != 1 else ''}"
    src = (book['title'] + (f', pages {start}-{end}' if start else '')) if book else "no book (the writer's own knowledge)"
    st.markdown(f"**{what}** · writer {provider} · source: {src}{' · with your prompt' if options['prompt'] else ''}\n\n"
                f"Estimated cost **about ${estimate:.2f}**, time **about {minutes} minutes**. A run stops by itself at ${COST_CAP:.0f}; finished PDFs are kept.")
    if errors: st.info('Still needed: ' + ' '.join(errors))
    if st.button('Generate', type='primary', disabled=bool(errors)):
        try: options['pyq'] = {t: {'urls': got} if kind == 'Links' else {'texts': [pyq.file_text(f.name, f.getvalue())[:120_000] for f in got]}
                               for t, (kind, got) in sources.items()}
        except Exception as e: st.error(f'A PYQ file could not be read ({type(e).__name__}: {e}). Save it again as PDF or .docx and retry.'); st.stop()
        run_id = jobs.create_run(mode, book['id'] if book else None, (start and int(start), end and int(end)), provider, options, user())
        st.success(f'Run #{run_id} started.')
        st.page_link('views/runs.py', label='Open the Runs page to follow it', icon='📄')

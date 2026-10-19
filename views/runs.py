"""Runs page: find a run (search and filters), follow its PDFs, review notes, download, resume, cancel, regenerate, delete."""
import io, json, re, zipfile
import openpyxl
import pandas as pd
import pymupdf
import streamlit as st
import db, jobs, pipeline
from config import STALE_SECONDS
from ui import can_manage, user

TOPIC_CHIP = {'queued': '⏳ Waiting', 'running': '⚙️ Working', 'done': '✅ Ready', 'warnings': '✅ Ready · notes to review', 'failed': '❌ Failed', 'stopped': '⛔ Stopped'}
RUN_STATUS = {'queued': 'Waiting', 'running': 'Working', 'done': 'Done', 'partial': 'Partly failed', 'failed': 'Failed',
              'stopped': 'Stopped (cost cap)', 'cancelled': 'Cancelled', 'interrupted': 'Interrupted'}
HEADER = ['Topic', 'File', 'Mode', 'Writer', 'Status', 'Cost (USD)', 'PYQs', 'Practice', 'Sample paper Q', 'Worked examples', 'Figures', 'Notes']
LIST_SQL = """select r.*, extract(epoch from now() - r.heartbeat_at) as age, count(t.id) as n,
                     count(t.id) filter (where t.status in ('done', 'warnings')) as ready, count(t.id) filter (where t.status = 'failed') as bad
              from runs r left join run_topics t on t.run_id = r.id group by r.id order by r.id desc limit 300"""


@st.cache_data(ttl=600, max_entries=60, show_spinner=False)
def fetch(path):
    return db.download('outputs', path)


def status(run):
    return 'interrupted' if run['status'] == 'running' and (run['age'] or 0) > STALE_SECONDS else run['status']


def title(run):
    return run.get('title') or ', '.join((run['options'] or {}).get('topics', [])[:3]) or f"Run {run['id']}"


def friendly(error):
    """What went wrong, in words, and what to do about it. The technical text stays available under 'Details'."""
    e = error or ''
    if 'cost cap' in e: return 'Stopped: the run reached its cost cap. **Resume** gives it another $5.'
    if e == 'cancelled': return 'Cancelled.'
    if re.search(r'Authentication|PermissionDenied|401|403|api.key', e, re.I): return 'The AI provider rejected the key. Check the app secrets.'
    if re.search(r'NotFound|404|model.*(not found|does not exist)', e, re.I): return 'The AI provider does not know the model name. Check the model in config.py.'
    if re.search(r'RateLimit|429|overloaded|529', e, re.I): return 'The AI provider is busy or limited the requests. **Resume** in a few minutes.'
    if 'rendering failed' in e: return 'The PDF could not be drawn. **Resume** tries again without new model calls.'
    if 'could not produce a usable' in e: return 'The writer could not produce a usable part of this PDF, even after asking again. **Resume** retries that part; finished parts are kept.'
    return 'Something went wrong. **Resume** tries again; finished parts are kept and not paid for twice.'


def count(x, types):
    """How many blocks of the given types a content JSON holds, at any depth."""
    if isinstance(x, dict): return (x.get('type') in types) + sum(count(v, types) for v in x.values())
    return sum(count(v, types) for v in x) if isinstance(x, list) else 0


def build_zip(run, topics):
    """All finished PDFs plus INDEX.xlsx (one row per PDF, with counts and notes), in memory."""
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(HEADER)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for t in (t for t in topics if t['pdf_path']):
            c = json.loads(fetch(t['json_path']))
            name = f"{t['position'] + 1:02d}_" + (re.sub(r'[^\w]+', '_', t['name']).strip('_')[:80] or 'topic') + '.pdf'   # numbered: no two topics share a name
            z.writestr(name, fetch(t['pdf_path']))
            ws.append([t['name'], name, run['mode'], run['model'], t['status'], float(t['cost_usd']), len(c.get('pyqs', [])), len(c.get('practice', [])),
                       len((c.get('sample_paper') or {}).get('questions', [])), count(c, ('example', 'worked_example')), count(c, ('figure',)), '; '.join(t['warnings'])])
        index = io.BytesIO(); wb.save(index); z.writestr('INDEX.xlsx', index.getvalue())
    return buf.getvalue()


def topic_card(run, t):
    with st.container(border=True):
        st.markdown(f"**{t['name']}** · {TOPIC_CHIP[t['status']]}" + (f" · *{t['step']}*" if t['status'] == 'running' and t['step'] else '') + f" · ${float(t['cost_usd']):.2f}")
        if t['error']:
            st.error(friendly(t['error']))
            with st.expander('Details'):
                st.code(t['error'], language=None, wrap_lines=True)
                for f in db.sql("select name, output from steps where run_topic_id=%s and name like '%%\\_failed' escape '\\'", (t['id'],)):
                    st.download_button(f"Download the model's unusable reply ({f['name'][:-7]})", json.dumps(f['output'], ensure_ascii=False, indent=1),
                                       file_name=f"run{run['id']}_{f['name']}.json", key=f"raw{t['id']}{f['name']}")
        if t['warnings']:
            with st.expander(f"⚠️ {len(t['warnings'])} note{'s' if len(t['warnings']) != 1 else ''} to review"):
                st.markdown('\n'.join(f'- {w}' for w in t['warnings']))
        if not t['pdf_path']: return
        c1, c2, c3 = st.columns([1, 1, 2])
        stem = re.sub(r'\W+', '_', t['name']).strip('_')
        c1.download_button('⬇ Download PDF', fetch(t['pdf_path']), file_name=stem + '.pdf', mime='application/pdf', key=f"pdf{t['id']}", type='primary',
                           on_click=db.event, args=(user(), 'downloaded', run['id']), kwargs={'file': stem + '.pdf'})
        c2.download_button('Download JSON', fetch(t['json_path']), file_name=stem + '.json', key=f"json{t['id']}")
        if c3.toggle('Preview first pages', key=f"pv{t['id']}"):
            doc = pymupdf.open(stream=fetch(t['pdf_path']), filetype='pdf')
            st.image([p.get_pixmap(dpi=60).tobytes('png') for p in list(doc)[:3]], width=260)
        with st.expander('Change this PDF'):
            feedback = st.text_area('Regenerate with your feedback (runs the model again and costs money)', key=f"fb{t['id']}", placeholder='e.g. more worked examples, simpler language')
            if st.button('Regenerate', key=f"rg{t['id']}", disabled=not feedback):
                options = dict(run['options'], feedback=feedback)
                if run['mode'] == 'gate': options['topics'] = [t['name']]
                new = jobs.create_run(run['mode'], run['book_id'], (run['scope_start'], run['scope_end']), options, user())
                st.success(f'Started run #{new}. Refresh the list to open it.')
            fixed = st.file_uploader('Or upload a corrected JSON (download it above, edit it, upload it here): re-renders without the model', type='json', key=f"up{t['id']}")
            if fixed and st.button('Re-render from this JSON', key=f"rr{t['id']}"):
                try: pipeline.rerender(t, run, json.loads(fixed.getvalue())); fetch.clear(); db.event(user(), 're-rendered', run['id'], topic=t['name']); st.success('Done: the PDF was replaced.')
                except Exception as e: st.error(f'Could not render: {e}')


def show(run_id, was_active):
    run = db.sql('select *, extract(epoch from now() - heartbeat_at) as age from runs where id=%s', (run_id,))
    if not run: st.info('This run was deleted.'); return
    run = run[0]
    topics = db.sql('select * from run_topics where run_id=%s order by position', (run_id,))
    s = status(run)
    active = s in ('queued', 'running')
    if was_active and not active: st.rerun()          # the run just finished: leave auto-refresh mode
    o = run['options'] or {}
    st.subheader(f"#{run['id']} · {title(run)}")
    scope = f" · pages {run['scope_start']}-{run['scope_end']}" if run['scope_start'] else ''
    st.caption(f"{'GATE' if run['mode'] == 'gate' else 'Non-GATE'} · {o.get('subject', '')} · writer {run['model']}, thinking {o.get('effort', 'medium')} · "
               f"started by {run['created_by']} on {run['created_at']:%d %b %Y, %H:%M} UTC" + (' · book used' + scope if run['book_id'] else ' · no book'))
    ready, bad = sum(t['pdf_path'] is not None for t in topics), sum(t['status'] == 'failed' for t in topics)
    c1, c2, c3 = st.columns(3)
    c1.metric('Status', RUN_STATUS.get(s, s))
    c2.metric('PDFs ready', f'{ready} of {len(topics)}' + (f' · {bad} failed' if bad else ''))
    c3.metric('Cost', f"${float(run['cost_usd']):.2f} of ${float(run['cost_cap']):.0f}")
    b1, b2, b3, b4 = st.columns(4)
    if active and b1.button('Cancel run'): jobs.cancel_run(run_id); st.rerun()
    if (s == 'interrupted' or any(t['status'] in ('stopped', 'failed') for t in topics)) and b2.button('Resume', type='primary', help='Retries what is unfinished. Finished parts are kept and not paid for twice.'):
        jobs.resume_run(run_id); st.rerun()
    if ready and b3.button('Prepare zip of all PDFs', help='All ready PDFs of this run plus INDEX.xlsx, a sheet that lists them with their counts and notes.'):
        st.session_state[f'zip{run_id}'] = build_zip(run, topics)
    if f'zip{run_id}' in st.session_state: b3.download_button('⬇ Download zip', st.session_state[f'zip{run_id}'], file_name=f'run_{run_id}.zip', mime='application/zip',
                                                              on_click=db.event, args=(user(), 'downloaded', run_id), kwargs={'file': f'run_{run_id}.zip'})
    if can_manage(run['created_by']):
        with b4.popover('Delete run'):
            if st.button('Yes, delete the run and its files', key=f'delrun{run_id}'):
                db.remove('outputs', [p for t in topics for p in (t['pdf_path'], t['json_path']) if p])
                db.sql('delete from runs where id=%s', (run_id,)); db.event(user(), 'deleted run', run_id, title=title(run))
                st.session_state.pop('runs_table', None); st.rerun()
    for t in topics: topic_card(run, t)
    with st.expander('Log'):
        rows = db.sql('select l.at, t.name, l.text from logs l left join run_topics t on t.id = l.run_topic_id where l.run_id=%s order by l.id desc limit 400', (run_id,))
        st.code('\n'.join(f"{r['at']:%H:%M:%S}  " + (f"[{r['name'][:30]}] " if r['name'] else '') + r['text'] for r in rows) or 'Nothing logged yet.', language=None, wrap_lines=True)
        st.caption('Newest first, times in UTC.')


st.title('Runs')
runs = db.sql(LIST_SQL)
if not runs: st.info('Nothing yet. Start a run on the Generate page.'); st.stop()

f1, f2, f3, f4, f5 = st.columns([3, 2, 1.3, 1.2, 0.8], vertical_alignment='bottom')
query = f1.text_input('Search', placeholder='topic, subject or person').strip().lower()
wanted = f2.multiselect('Status', ['Working', 'Done', 'Partly failed', 'Failed', 'Stopped / cancelled'], placeholder='All statuses')
kind = f3.selectbox('Type', ['All', 'GATE', 'Non-GATE'])
mine = f4.toggle('Only mine')
f5.button('↻', help='Refresh the list')
GROUP = {'queued': 'Working', 'running': 'Working', 'interrupted': 'Working', 'done': 'Done', 'partial': 'Partly failed', 'failed': 'Failed',
         'stopped': 'Stopped / cancelled', 'cancelled': 'Stopped / cancelled'}
shown = [r for r in runs
         if (not query or query in ' '.join([title(r), (r['options'] or {}).get('subject', ''), r['created_by'] or '']).lower())
         and (not wanted or GROUP.get(status(r)) in wanted) and (kind == 'All' or (r['mode'] == 'gate') == (kind == 'GATE'))
         and (not mine or (r['created_by'] or '').lower() == user())]
if not shown: st.info('No run matches these filters.'); st.stop()

table = pd.DataFrame([{'Run': f"#{r['id']}", 'Topics': title(r), 'Type': 'GATE' if r['mode'] == 'gate' else 'Non-GATE', 'Status': RUN_STATUS.get(status(r), status(r)),
                       'PDFs': f"{r['ready']} of {r['n']} ready" + (f" · {r['bad']} failed" if r['bad'] else ''), 'Writer': r['model'],
                       'By': (r['created_by'] or '').split('@')[0], 'Started': r['created_at'].strftime('%d %b %H:%M'), 'Cost': f"${float(r['cost_usd']):.2f}"} for r in shown])
event = st.dataframe(table, hide_index=True, width='stretch', height=min(38 * len(shown) + 38, 290), on_select='rerun', selection_mode='single-row', key='runs_table')
rows = event.selection.rows if event and event.selection else []
chosen = shown[rows[0]] if rows and rows[0] < len(shown) else shown[0]
st.caption('Click a row to open that run.' if not rows else '')
live = status(chosen) in ('queued', 'running')
st.fragment(show, run_every=5 if live else None)(chosen['id'], live)

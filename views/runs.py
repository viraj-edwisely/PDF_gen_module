"""Runs page: progress of every run, warnings, previews, downloads, regenerate, resume and cancel."""
import io, json, re, zipfile
import pymupdf
import openpyxl
import streamlit as st
import db, jobs, pipeline
from config import STALE_SECONDS
from ui import user

CHIP = {'queued': '⏳ queued', 'running': '⚙️ running', 'done': '✅ done', 'warnings': '⚠️ done, with warnings', 'failed': '❌ failed', 'stopped': '⛔ stopped'}
HEADER = ['Topic', 'File', 'Mode', 'Writer', 'Status', 'Cost (USD)', 'PYQs', 'Practice', 'Sample paper Q', 'Worked examples', 'Figures', 'Warnings']


@st.cache_data(ttl=600, show_spinner=False)
def fetch(path):
    return db.download('outputs', path)


def count(x, types):
    """How many blocks of the given types a content JSON holds, at any depth."""
    if isinstance(x, dict): return (x.get('type') in types) + sum(count(v, types) for v in x.values())
    return sum(count(v, types) for v in x) if isinstance(x, list) else 0


def build_zip(run, topics):
    """All finished PDFs plus INDEX.xlsx, in memory."""
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(HEADER)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for t in (t for t in topics if t['pdf_path']):
            c = json.loads(fetch(t['json_path']))
            name = re.sub(r'[^A-Za-z0-9]+', '_', t['name']).strip('_')[:80] + '.pdf'
            z.writestr(name, fetch(t['pdf_path']))
            ws.append([t['name'], name, run['mode'], f"{run['provider']} ({run['model']})", t['status'], float(t['cost_usd']), len(c.get('pyqs', [])), len(c.get('practice', [])),
                       len((c.get('sample_paper') or {}).get('questions', [])), count(c, ('example', 'worked_example')), count(c, ('figure', 'image')), '; '.join(t['warnings'])])
        index = io.BytesIO(); wb.save(index); z.writestr('INDEX.xlsx', index.getvalue())
    return buf.getvalue()


def topic_card(run, t):
    with st.container(border=True):
        st.markdown(f"**{t['name']}** · {CHIP[t['status']]}" + (f" · {t['step']}" if t['status'] == 'running' and t['step'] else '') + f" · ${float(t['cost_usd']):.2f}")
        if t['error']: st.error(t['error'])
        for w in t['warnings']: st.warning(w)
        if not t['pdf_path']: return
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.download_button('⬇ Download PDF', fetch(t['pdf_path']), file_name=re.sub(r'\W+', '_', t['name']) + '.pdf', mime='application/pdf', key=f"pdf{t['id']}", type='primary')
        c2.download_button('Download JSON', fetch(t['json_path']), file_name=re.sub(r'\W+', '_', t['name']) + '.json', key=f"json{t['id']}")
        if c3.toggle('Preview first pages', key=f"pv{t['id']}"):
            doc = pymupdf.open(stream=fetch(t['pdf_path']), filetype='pdf')
            st.image([p.get_pixmap(dpi=60).tobytes('png') for p in list(doc)[:3]], width=260)
        with st.expander('Change this PDF'):
            feedback = st.text_area('Regenerate with feedback (runs the model again and costs money)', key=f"fb{t['id']}", placeholder='e.g. more worked examples, simpler language')
            if st.button('Regenerate', key=f"rg{t['id']}", disabled=not feedback):
                options = dict(run['options'], feedback=feedback)
                if run['mode'] == 'gate': options['topics'] = [t['name']]
                new = jobs.create_run(run['mode'], run['book_id'], (run['scope_start'], run['scope_end']), run['provider'], options, user())
                st.success(f'Started run #{new}. Pick it in the list above.')
            fixed = st.file_uploader('Or upload a corrected JSON (download it above, edit it, upload it here): re-renders without the model', type='json', key=f"up{t['id']}")
            if fixed and st.button('Re-render from this JSON', key=f"rr{t['id']}"):
                try: pipeline.rerender(t, run, json.loads(fixed.getvalue())); fetch.clear(); st.success('Done: the PDF was replaced.')
                except Exception as e: st.error(f'Could not render: {e}')


def show(run_id, was_active):
    run = db.sql('select *, extract(epoch from now() - heartbeat_at) as age from runs where id=%s', (run_id,))[0]
    topics = db.sql('select * from run_topics where run_id=%s order by position', (run_id,))
    interrupted = run['status'] == 'running' and (run['age'] or 0) > STALE_SECONDS
    active = run['status'] in ('queued', 'running') and not interrupted
    if was_active and not active: st.rerun()          # the run just finished: leave auto-refresh mode
    label = 'interrupted' if interrupted else run['status']
    c1, c2, c3 = st.columns(3)
    c1.metric('Status', label)
    c2.metric('Cost', f"${float(run['cost_usd']):.2f} of ${float(run['cost_cap']):.0f}")
    c3.metric('PDFs finished', f"{sum(t['pdf_path'] is not None for t in topics)} of {len(topics)}")
    b1, b2, b3, b4 = st.columns(4)
    if active and b1.button('Cancel run'): jobs.cancel_run(run_id); st.rerun()
    if (interrupted or any(t['status'] in ('stopped', 'failed') for t in topics)) and b2.button('Resume'): jobs.resume_run(run_id); st.rerun()
    if any(t['pdf_path'] for t in topics) and b3.button('Prepare zip with INDEX'):
        st.session_state[f'zip{run_id}'] = build_zip(run, topics)
    if f'zip{run_id}' in st.session_state: b3.download_button('Download zip', st.session_state[f'zip{run_id}'], file_name=f'run_{run_id}.zip', mime='application/zip')
    with b4.popover('Delete run'):
        if st.button('Yes, delete the run and its files', key=f'delrun{run_id}'):
            db.remove('outputs', [p for t in topics for p in (t['pdf_path'], t['json_path']) if p])
            db.sql('delete from runs where id=%s', (run_id,)); st.rerun()
    st.caption(f"{run['mode'].upper()} · {run['provider']} ({run['model']}) · started by {run['created_by']}")
    for t in topics: topic_card(run, t)
    with st.expander('Log'):
        rows = db.sql('select l.at, t.name, l.text from logs l left join run_topics t on t.id = l.run_topic_id where l.run_id=%s order by l.id desc limit 300', (run_id,))
        st.code('\n'.join(f"{r['at']:%H:%M:%S}  " + (f"[{r['name'][:30]}] " if r['name'] else '') + r['text'] for r in rows) or 'Nothing logged yet.', language=None, wrap_lines=True)
        st.caption('Newest first, times in UTC.')


st.title('Runs')
runs = db.sql('select * from runs order by id desc limit 40')
if not runs: st.info('Nothing yet. Start a run on the Generate page.'); st.stop()
chosen = st.selectbox('Run', runs, format_func=lambda r: f"#{r['id']} · {r['mode'].upper()} · {r['provider']} · {r['created_at']:%d %b %H:%M} · {r['created_by']} · {r['status']}")
live = chosen['status'] in ('queued', 'running')
st.fragment(show, run_every=5 if live else None)(chosen['id'], live)

"""Illustrations page: the library of pictures of real apparatus. A new picture is used in PDFs at once with an "Unreviewed" tag until a
person approves it here; a rejected picture is never used. Anyone signed in may approve or reject; who did it is recorded."""
import io, os, sys
import streamlit as st
from PIL import Image
import db
from ui import user

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'render'))
from marks import mark_parts    # noqa: E402

STATUS = {'pending': "⏳ In use with an 'Unreviewed' tag", 'approved': '✅ Approved', 'rejected': '❌ Rejected'}


@st.cache_data(ttl=600, max_entries=200, show_spinner=False)
def picture(path, marks):
    """The picture as a PDF shows it: with the numbered markers the app puts on the parts (older pictures carry their own numbers)."""
    im = Image.open(io.BytesIO(db.download('illustrations', path)))
    if marks: im = mark_parts(im, marks)
    out = io.BytesIO(); im.save(out, 'PNG')
    return out.getvalue()


def decide(concept, status, note):
    db.sql('update illustrations set status=%s, review=coalesce(nullif(%s, \'\'), review), reviewed_by=%s, reviewed_at=now() where concept=%s', (status, note, user(), concept))
    db.event(user(), f'illustration {status}', concept=concept)


st.title('Illustrations')
st.caption('Pictures for what students must recognise (an engine, a pump, tray types, a heat-exchanger cut-away). Each concept is drawn once, checked by the model, '
           'numbered by the app and used in PDFs at once with an Unreviewed tag. Check that each number sits on the right part and that the apparatus is drawn correctly, '
           'then approve it (the tag goes when a PDF is regenerated) or reject it (PDFs stop using it).')
rows = db.sql('select * from illustrations order by (status = \'pending\') desc, created_at desc')
if not rows: st.info('No illustrations yet. Turn on "Draw new illustrations" on the Generate page for a topic that needs one.'); st.stop()
show = st.segmented_control('Show', ['Waiting', 'Approved', 'Rejected', 'All'], default='Waiting')
want = {'Waiting': ('pending',), 'Approved': ('approved',), 'Rejected': ('rejected',), 'All': tuple(STATUS)}[show or 'All']
for r in (r for r in rows if r['status'] in want):
    with st.container(border=True):
        c1, c2 = st.columns([3, 2])
        try: c1.image(picture(r['path'], r['marks'] or []), width='stretch')
        except Exception: c1.warning('The picture could not be loaded.')
        c2.markdown(f"**{r['title'] or r['concept']}** · {STATUS.get(r['status'], r['status'])}  \n`{r['concept']}`")
        if r['description']: c2.caption(r['description'])
        if r['parts']: c2.markdown('\n'.join(f'{k}. {p}' for k, p in enumerate(r['parts'], 1)))
        if r['review']: c2.info(f"Check: {r['review']}")
        if r['reviewed_by']: c2.caption(f"{STATUS.get(r['status'], r['status'])} by {r['reviewed_by']} on {r['reviewed_at']:%d %b %Y}")
        note = c2.text_input('Note (optional)', key=f"note{r['concept']}")
        b1, b2 = c2.columns(2)
        if r['status'] != 'approved' and b1.button('Approve', key=f"ok{r['concept']}", type='primary'): decide(r['concept'], 'approved', note); st.rerun()
        if r['status'] != 'rejected' and b2.button('Reject', key=f"no{r['concept']}"): decide(r['concept'], 'rejected', note); st.rerun()

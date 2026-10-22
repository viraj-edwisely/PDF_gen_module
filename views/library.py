"""Library page: upload books (processed in the background), review units and page offset, delete."""
import hashlib
import pandas as pd
import streamlit as st
import db
from config import MAX_BOOK_MB
from ui import can_manage, user

KINDS = {'textbook': 'Textbook', 'handbook': 'Reference handbook'}

st.title('Library')
st.caption('Upload a textbook once. Everyone on the team can generate PDFs from it. Processing runs in the background: you can leave this page.')

with st.form('upload', clear_on_submit=True):
    pdf = st.file_uploader('Book PDF', type='pdf')
    kind = st.radio('Type', list(KINDS), format_func=KINDS.get, horizontal=True,
                    help='Textbook: the source a PDF is written from. Reference handbook: only used to check that the plan covers everything standard on a topic; nothing is copied from it.')
    c1, c2, c3 = st.columns(3)
    title, subject, paper = c1.text_input('Title'), c2.text_input('Subject (e.g. Operating System)'), c3.text_input('GATE paper code (optional, e.g. CS)')
    submitted = st.form_submit_button('Upload')
if submitted:
    if not (pdf and title and subject): st.error('Choose a PDF and fill in the title and subject.')
    elif pdf.size > MAX_BOOK_MB * 1024 * 1024: st.error(f'The file is larger than {MAX_BOOK_MB} MB.')
    else:
        data = pdf.getvalue(); digest = hashlib.sha256(data).hexdigest()
        dup = db.sql('select title from books where file_hash=%s', (digest,))
        if dup: st.error(f'This PDF is already in the library as "{dup[0]["title"]}".')
        else:
            book_id = db.sql("insert into books (title, subject, paper, kind, file_hash, uploaded_by, status, step) values (%s,%s,%s,%s,%s,%s,'uploading','Uploading') returning id",
                             (title, subject, paper.upper() or None, kind, digest, user()))[0]['id']
            try:
                with st.spinner('Uploading...'): db.upload('books', f'{book_id}.pdf', data, 'application/pdf')
                db.sql("update books set storage_path=%s, status='queued', step='Waiting' where id=%s", (f'{book_id}.pdf', book_id))
                db.event(user(), 'uploaded book', title=title, mb=round(pdf.size / 2**20, 1))
                st.success('Uploaded. It is being processed in the background; it appears as ready below in a few minutes.')
            except Exception as e:
                db.sql('delete from books where id=%s', (book_id,)); st.error(f'The upload failed: {e}')


def book_list():
    books = db.sql('select * from books order by created_at desc')
    if not books: st.info('No books yet.'); return
    for b in books:
        icon = {'ready': '✅', 'failed': '❌'}.get(b['status'], '⏳')
        with st.expander(f"{icon} {b['title']} · {b['subject']} · {KINDS[b['kind']]}" + (f" · {b['page_count']} pages" if b['page_count'] else ''), expanded=b['status'] not in ('ready', 'failed')):
            kind = st.selectbox('Type', list(KINDS), index=list(KINDS).index(b['kind']), format_func=KINDS.get, key=f"kind{b['id']}")
            if kind != b['kind']: db.sql('update books set kind=%s where id=%s', (kind, b['id'])); st.rerun()
            st.caption(f"Uploaded by {b['uploaded_by']} on {b['created_at']:%d %b %Y}" + (f" · paper {b['paper']}" if b['paper'] else ''))
            if b['status'] in ('queued', 'processing', 'uploading'):
                st.progress(float(b['progress'] or 0), b['step'] or 'Waiting')
            elif b['status'] == 'failed':
                st.warning(b['error'] or 'Processing was interrupted.')
                if b['storage_path'] and st.button('Process again', key=f"re{b['id']}"):
                    db.sql("update books set status='queued', step='Waiting', progress=0, error=null where id=%s", (b['id'],)); st.rerun()
            else:
                offset = st.number_input('Extra pages before page 1 (advanced)', value=int(b['page_offset']), step=1, key=f"off{b['id']}",
                                         help='Detected automatically. Change it only if a page range picks the wrong pages: enter how many PDF pages (cover, contents) come before the book\'s printed page 1.')
                units = pd.DataFrame(db.sql('select name, start_page, end_page from units where book_id=%s order by start_page', (b['id'],)), columns=['name', 'start_page', 'end_page'])
                st.caption('Units, in printed page numbers. They appear as choices on the Generate page. Edit, add or remove rows; with none, use page ranges.')
                edited = st.data_editor(units, num_rows='dynamic', key=f"units{b['id']}", width='stretch',
                                        column_config={'name': 'Unit name', 'start_page': st.column_config.NumberColumn('First page', min_value=1, step=1),
                                                       'end_page': st.column_config.NumberColumn('Last page', min_value=1, step=1)})
                if st.button('Save units and offset', key=f"save{b['id']}"):
                    rows = edited.dropna()
                    db.sql('update books set page_offset=%s where id=%s', (offset, b['id']))
                    db.sql('delete from units where book_id=%s', (b['id'],))
                    db.many('insert into units (book_id, name, start_page, end_page) values (%s,%s,%s,%s)', [(b['id'], r['name'], int(r['start_page']), int(r['end_page'])) for _, r in rows.iterrows()])
                    st.success('Saved.')
            if can_manage(b['uploaded_by']):
                with st.popover('Delete book'):
                    st.write('This removes the book, its text and its search index. Finished PDFs from earlier runs are kept.')
                    if st.button('Yes, delete', key=f"del{b['id']}"):
                        db.remove('books', [b['storage_path']] if b['storage_path'] else [])
                        db.sql('delete from books where id=%s', (b['id'],)); db.event(user(), 'deleted book', title=b['title'])
                        st.rerun()


st.subheader('Books')
busy = bool(db.sql("select 1 from books where status in ('queued', 'processing', 'uploading') limit 1"))
st.fragment(book_list, run_every=4 if busy else None)()

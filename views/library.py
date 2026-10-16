"""Library page: upload books, review units and page offset, delete."""
import hashlib
import pandas as pd
import streamlit as st
import db, ingest
from config import MAX_BOOK_MB
from ui import user

st.title('Library')
st.caption('Upload a textbook once. Everyone on the team can generate PDFs from it.')


def process(book_id, data):
    bar = st.progress(0.0, 'Starting')
    try:
        ingest.ingest(book_id, data, lambda frac, msg: bar.progress(frac, msg))
        st.success('Book is ready.')
    except Exception as e:
        st.error(f'Processing failed: {e}')


with st.form('upload', clear_on_submit=True):
    pdf = st.file_uploader('Book PDF', type='pdf')
    c1, c2, c3 = st.columns(3)
    title, subject, paper = c1.text_input('Title'), c2.text_input('Subject (e.g. Operating System)'), c3.text_input('GATE paper code (optional, e.g. CS)')
    submitted = st.form_submit_button('Upload and process')
if submitted:
    if not (pdf and title and subject): st.error('Choose a PDF and fill in the title and subject.')
    elif pdf.size > MAX_BOOK_MB * 1024 * 1024: st.error(f'The file is larger than {MAX_BOOK_MB} MB.')
    else:
        data = pdf.getvalue(); digest = hashlib.sha256(data).hexdigest()
        dup = db.sql('select title from books where file_hash=%s', (digest,))
        if dup: st.error(f'This PDF is already in the library as "{dup[0]["title"]}".')
        else:
            book_id = db.sql('insert into books (title, subject, paper, file_hash, uploaded_by) values (%s,%s,%s,%s,%s) returning id', (title, subject, paper.upper() or None, digest, user()))[0]['id']
            db.upload('books', f'{book_id}.pdf', data, 'application/pdf')
            db.sql('update books set storage_path=%s where id=%s', (f'{book_id}.pdf', book_id))
            process(book_id, data)

st.subheader('Books')
books = db.sql('select * from books order by created_at desc')
if not books: st.info('No books yet.')
for b in books:
    icon = {'ready': '✅', 'processing': '⏳', 'failed': '❌'}[b['status']]
    with st.expander(f"{icon} {b['title']} · {b['subject']} · {b['page_count']} pages"):
        st.caption(f"Uploaded by {b['uploaded_by']} on {b['created_at']:%d %b %Y}" + (f" · paper {b['paper']}" if b['paper'] else ''))
        if b['status'] != 'ready':
            st.warning(b['error'] or 'Processing was interrupted.')
            if st.button('Process again', key=f"re{b['id']}"): process(b['id'], db.download('books', b['storage_path']))
        else:
            offset = st.number_input('Extra pages before page 1 (advanced)', value=int(b['page_offset']), step=1, key=f"off{b['id']}",
                                     help='Detected automatically. Change it only if a page range picks the wrong pages: enter how many PDF pages (cover, contents) come before the book\'s printed page 1.')
            units = pd.DataFrame(db.sql('select name, start_page, end_page from units where book_id=%s order by start_page', (b['id'],)), columns=['name', 'start_page', 'end_page'])
            st.caption('Units (printed page numbers). Edit, add or remove rows; with none, use page ranges when generating.')
            edited = st.data_editor(units, num_rows='dynamic', key=f"units{b['id']}", width='stretch')
            if st.button('Save units and offset', key=f"save{b['id']}"):
                rows = edited.dropna()
                db.sql('update books set page_offset=%s where id=%s', (offset, b['id']))
                db.sql('delete from units where book_id=%s', (b['id'],))
                db.many('insert into units (book_id, name, start_page, end_page) values (%s,%s,%s,%s)', [(b['id'], r['name'], int(r['start_page']), int(r['end_page'])) for _, r in rows.iterrows()])
                st.success('Saved.')
        with st.popover('Delete book'):
            st.write('This removes the book, its text and its search index. Finished PDFs from earlier runs are kept.')
            if st.button('Yes, delete', key=f"del{b['id']}"):
                db.remove('books', [b['storage_path']] if b['storage_path'] else [])
                db.sql('delete from books where id=%s', (b['id'],))
                st.rerun()

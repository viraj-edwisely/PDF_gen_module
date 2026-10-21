"""Edwisely PDF builder: entry point. Checks the secrets, creates the tables, starts the background workers, shows the pages."""
import streamlit as st
import db, jobs, ui
from config import secret

st.set_page_config(page_title='Edwisely PDF Builder', page_icon='📘', layout='wide')

REQUIRED = ('DATABASE_URL', 'SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY')   # the writer and the book search both use OpenAI
missing = [k for k in REQUIRED if not secret(k)]
if missing:
    st.error('Setup is incomplete. Add these in the app secrets (see README.md): ' + ', '.join(missing))
    st.stop()


@st.cache_resource
def start():
    db.init()
    jobs.start_workers()
    return True


start()
ui.require_access()      # after start(): the accounts live in the database
st.navigation([st.Page('views/generate.py', title='Generate', icon='✨', default=True),
               st.Page('views/runs.py', title='Runs', icon='📄'),
               st.Page('views/library.py', title='Library', icon='📚'),
               st.Page('views/illustrations.py', title='Illustrations', icon='🖼️'),
               st.Page('views/usage.py', title='Usage', icon='📊')]
              + ([st.Page('views/admin.py', title='Admin', icon='🔑')] if ui.is_admin() else [])).run()

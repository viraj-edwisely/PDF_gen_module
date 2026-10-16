"""Edwisely PDF builder: entry point. Checks the secrets, creates the tables, starts the background workers, shows the pages."""
import streamlit as st
import db, jobs, ui
from config import PROVIDERS, secret

st.set_page_config(page_title='Edwisely PDF Builder', page_icon='📘', layout='wide')
ui.require_access()

REQUIRED = ('DATABASE_URL', 'SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY')   # OpenAI is always needed for book search
missing = [k for k in REQUIRED if not secret(k)]
if missing or not any(secret(p['key']) for p in PROVIDERS.values()):
    st.error('Setup is incomplete. Add these in the app secrets (see README.md): ' + ', '.join(missing + ([] if any(secret(p['key']) for p in PROVIDERS.values()) else ['at least one of ' + ', '.join(p['key'] for p in PROVIDERS.values())])))
    st.stop()


@st.cache_resource
def start():
    db.init()
    jobs.start_workers()
    return True


start()
st.navigation([st.Page('views/generate.py', title='Generate', icon='✨', default=True),
               st.Page('views/runs.py', title='Runs', icon='📄'),
               st.Page('views/library.py', title='Library', icon='📚')]).run()

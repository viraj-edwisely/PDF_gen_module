"""Small helpers shared by the pages: who is signed in, who may use the app, who may delete what."""
import streamlit as st
from config import secret


def _list(name, default=''):
    return {x.strip().lower() for x in str(secret(name) or default).split(',') if x.strip()}


def user():
    """The viewer's work email, as typed on the first page (see require_access)."""
    return st.session_state.get('email', '')


def require_access():
    """Ask once per browser session for the viewer's work email and stop the page unless it is in ALLOWED_EMAILS
    or its domain in ALLOWED_DOMAINS (default edwisely.com). The email is not verified: who can open the app at all
    is decided by keeping the app private on Community Cloud (Settings → Sharing)."""
    if user(): return st.sidebar.caption(f'Working as {user()}')
    st.title('Edwisely PDF Builder')
    with st.form('who'):
        email = st.text_input('Your work email', placeholder='name@edwisely.com', autocomplete='email').strip().lower()
        sent = st.form_submit_button('Continue', type='primary')
    if sent and email:
        if email in _list('ALLOWED_EMAILS') or email.split('@')[-1] in _list('ALLOWED_DOMAINS', 'edwisely.com'):
            st.session_state.email = email; st.rerun()
        st.error(f'{email} does not have access to this app. Ask an admin to add you.')
    st.stop()


def can_manage(owner):
    """Delete and other destructive actions: the person who created the item, or an admin (ADMINS)."""
    return user() == (owner or '').lower() or user() in _list('ADMINS')

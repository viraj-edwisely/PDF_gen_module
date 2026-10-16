"""Small helpers shared by the pages: who is signed in, who may use the app, who may delete what."""
import streamlit as st
from config import secret


def _list(name, default=''):
    return {x.strip().lower() for x in str(secret(name) or default).split(',') if x.strip()}


def user():
    """The viewer's email (Community Cloud private app), or 'local' on a laptop run that allows it."""
    return (getattr(st.user, 'email', None) or 'local').lower()


def require_access():
    """Stop the page unless the viewer is allowed: an email in ALLOWED_EMAILS or a domain in ALLOWED_DOMAINS
    (default edwisely.com). Without a signed-in email (a public app, or a laptop) only ALLOW_LOCAL = "true" lets you in."""
    email = getattr(st.user, 'email', None)
    if not email:
        if str(secret('ALLOW_LOCAL')).lower() == 'true': return
        st.error('Sign-in is required. Make the app private in Streamlit Community Cloud (Settings → Sharing) and invite your team. '
                 'For a run on your own computer, add ALLOW_LOCAL = "true" to .streamlit/secrets.toml.')
        st.stop()
    email = email.lower()
    if email not in _list('ALLOWED_EMAILS') and email.split('@')[-1] not in _list('ALLOWED_DOMAINS', 'edwisely.com'):
        st.error(f'{email} does not have access to this app. Ask an admin to add you.'); st.stop()


def can_manage(owner):
    """Delete and other destructive actions: the person who created the item, or an admin (ADMINS)."""
    me = user()
    return me == (owner or '').lower() or me in _list('ADMINS') or me == 'local'

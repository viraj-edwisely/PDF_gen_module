"""Small helpers shared by the pages."""
import streamlit as st


def user():
    """The viewer's email (Community Cloud private app), or 'local' when running on a laptop."""
    return getattr(st.user, 'email', None) or 'local'

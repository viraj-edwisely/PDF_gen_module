"""Sign-in and permissions. People are added by an admin on the Admin page and sign in with their email and password;
passwords are stored only as salted scrypt hashes. With no accounts yet, the sign-in page creates the first admin."""
import hashlib, hmac, secrets, time
import streamlit as st
import db

MIN_PASSWORD = 10


def hash_password(password):
    salt = secrets.token_bytes(16)
    return f'scrypt${salt.hex()}${hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()}'


def check_password(password, stored):
    _, salt, digest = stored.split('$')
    return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex(), digest)


def new_password():
    return secrets.token_urlsafe(9)        # 12 characters


def user():
    """The signed-in person's email."""
    return st.session_state.get('email', '')


def is_admin():
    return st.session_state.get('admin', False)


def can_manage(owner):
    """Delete and other destructive actions: the person who created the item, or an admin."""
    return user() == (owner or '').lower() or is_admin()


def require_access():
    """Stop the page unless someone is signed in with an active account (checked on every page load, so a
    deactivated person is signed out at once)."""
    s = st.session_state
    if user():
        row = db.sql('select is_admin from users where email=%s and active', (user(),))
        if row: s.admin = row[0]['is_admin']; return _sidebar()
        s.clear()
    first = not db.sql('select 1 from users limit 1')
    st.title('Edwisely PDF Builder')
    with st.form('signin'):
        if first: st.info('There are no accounts yet. Create the first admin account (yours); add everyone else on the Admin page afterwards.')
        email = st.text_input('Email', autocomplete='email').strip().lower()
        password = st.text_input(f'Password (at least {MIN_PASSWORD} characters)' if first else 'Password', type='password')
        sent = st.form_submit_button('Create admin account' if first else 'Sign in', type='primary')
    if sent and first:
        if '@' not in email or len(password) < MIN_PASSWORD: st.error(f'Enter your email and a password of at least {MIN_PASSWORD} characters.')
        elif db.sql('insert into users (email, password_hash, is_admin, created_by) select %s,%s,true,%s where not exists (select 1 from users) returning email',
                    (email, hash_password(password), email)):
            s.email = email; db.event(email, 'sign in', first_admin=True); st.rerun()
        else: st.error('An account was created in the meantime. Reload the page and sign in.')
    elif sent:
        row = db.sql('select password_hash from users where email=%s and active', (email,))
        if row and check_password(password, row[0]['password_hash']):
            s.email = email; db.sql('update users set last_login=now() where email=%s', (email,)); db.event(email, 'sign in'); st.rerun()
        time.sleep(1); db.event(email, 'sign-in failed')
        st.error('Wrong email or password. Ask an admin to reset your password if you forgot it.')
    st.stop()


def _sidebar():
    st.sidebar.caption(f'Signed in as {user()}')
    with st.sidebar.popover('Change password'), st.form('password', clear_on_submit=True):
        old = st.text_input('Current password', type='password')
        new = st.text_input(f'New password (at least {MIN_PASSWORD} characters)', type='password')
        if st.form_submit_button('Change'):
            if not check_password(old, db.sql('select password_hash from users where email=%s', (user(),))[0]['password_hash']): st.error('The current password is wrong.')
            elif len(new) < MIN_PASSWORD: st.error(f'The new password needs at least {MIN_PASSWORD} characters.')
            else: db.sql('update users set password_hash=%s where email=%s', (hash_password(new), user())); db.event(user(), 'changed password'); st.success('Password changed.')
    st.sidebar.button('Sign out', on_click=st.session_state.clear)

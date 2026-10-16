"""Admin page (admins only): add people with a generated password, reset passwords, make admins, deactivate or delete accounts."""
import pandas as pd
import streamlit as st
import db
from ui import hash_password, is_admin, new_password, user

if not is_admin(): st.error('Only admins can open this page.'); st.stop()
st.title('Admin')


st.subheader('Add a person')
with st.form('add', clear_on_submit=True):
    c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment='bottom')
    email, name, admin = c1.text_input('Email').strip().lower(), c2.text_input('Name (optional)').strip(), c3.checkbox('Admin')
    if st.form_submit_button('Add and make a password', type='primary'):
        if '@' not in email: st.error('Enter a valid email.')
        elif db.sql('select 1 from users where email=%s', (email,)): st.error(f'{email} already has an account: select it below to reset the password.')
        else:
            password = new_password()
            db.sql('insert into users (email, name, password_hash, is_admin, created_by) values (%s,%s,%s,%s,%s)', (email, name or None, hash_password(password), admin, user()))
            db.event(user(), 'added person', person=email, admin=admin); st.session_state.new_password = (email, password)

if 'new_password' in st.session_state:
    email, password = st.session_state.new_password
    with st.container(border=True):
        st.success(f'New password for {email}. It is shown only now: copy the message below and send it to them.')
        st.code(f'You can now use the Edwisely PDF Builder.\nEmail: {email}\nPassword: {password}\n'
                'After signing in, choose a password of your own: sidebar → Change password.', language=None)
        st.button('Done, hide it', on_click=st.session_state.pop, args=('new_password',))

st.subheader('People')
people = db.sql('select * from users order by email')
table = pd.DataFrame({'Email': [p['email'] for p in people], 'Name': [p['name'] or '' for p in people],
                      'Role': ['Admin' if p['is_admin'] else 'Member' for p in people],
                      'Status': ['Active' if p['active'] else 'Deactivated' for p in people],
                      'Last sign-in': [f"{p['last_login']:%d %b %Y, %H:%M} UTC" if p['last_login'] else 'never' for p in people],
                      'Added': [f"{p['created_at']:%d %b %Y} by {p['created_by']}" for p in people]})
version = st.session_state.setdefault('people_version', 0)          # a new key clears the selection after a delete
picked = st.dataframe(table, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'people{version}').selection.rows
if not picked or picked[0] >= len(people): st.caption('Select a person to reset their password, change their role or remove them.'); st.stop()

p = people[picked[0]]
me = p['email'] == user()
st.markdown(f"**{p['email']}**" + (' (you: you cannot remove your own admin role or account)' if me else ''))
b1, b2, b3, b4 = st.columns(4)
if b1.button('Reset password', help='Makes a new password and shows it once; the old one stops working.'):
    password = new_password()
    db.sql('update users set password_hash=%s where email=%s', (hash_password(password), p['email']))
    db.event(user(), 'reset password', person=p['email']); st.session_state.new_password = (p['email'], password); st.rerun()
if b2.button('Remove admin role' if p['is_admin'] else 'Make admin', disabled=me):
    db.sql('update users set is_admin = not is_admin where email=%s', (p['email'],)); db.event(user(), 'changed role', person=p['email'], admin=not p['is_admin']); st.rerun()
if b3.button('Deactivate' if p['active'] else 'Activate', disabled=me, help='A deactivated person cannot sign in (and is signed out at once). Their runs, books and usage stay.'):
    db.sql('update users set active = not active where email=%s', (p['email'],)); db.event(user(), 'deactivated' if p['active'] else 'activated', person=p['email']); st.rerun()
with b4.popover('Delete account', disabled=me):
    st.write('The account is removed; the runs, books and usage history of this person stay.')
    if st.button('Yes, delete', key='delete_user'):
        db.sql('delete from users where email=%s', (p['email'],)); db.event(user(), 'deleted person', person=p['email'])
        st.session_state.people_version += 1; st.rerun()

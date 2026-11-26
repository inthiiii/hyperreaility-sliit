"""Sign-in screen, signed-in identity and the roles panel."""
from html import escape
from pathlib import Path

import streamlit as st

from project.auth import PERMISSIONS, ROLES, AuthError, User, UserStore, can, default_store_path
from project.auth.roles import roles_for
from project.ui.brand import brand_html


def current_user():
    """The verified user lives only in server-side session state; browsers cannot set it."""
    user = st.session_state.get('auth_user')
    return user if isinstance(user, User) else None


def needs_role(permission):
    return 'Requires: ' + ', '.join(roles_for(permission))


def _sign_in(store):
    try:
        user = store.authenticate(st.session_state.get('login_username', ''), st.session_state.get('login_password', ''))
        st.session_state['auth_user'] = user
        st.session_state['login_error'] = None
    except AuthError as error:
        st.session_state['login_error'] = str(error)
    st.session_state['login_password'] = ''


def sign_out():
    for key in ('auth_user', 'operator_label', 'review_note'):
        st.session_state.pop(key, None)


def render_login(root):
    store = UserStore(default_store_path(root))
    st.html('<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],'
            '[data-testid="stExpandSidebarButton"]{display:none}</style>'
            '<div class="relink-login-head">' + brand_html('xl', tagline=True) +
            '<h1>Bring the network back <em>faster</em>, together.</h1>'
            '<p>Field reports in, a checked and approved crew plan out, with the downtime it saves measured.</p></div>')
    _, middle, _ = st.columns([1, 1.15, 1])
    with middle, st.container(border=True):
        st.html('<div class="relink-login-title">Sign in to the recovery workspace</div>')
        if not store.exists():
            st.warning('No users are configured on this machine yet.')
            st.write('Create demo users (one per role) from the repository root:')
            st.code('python -m project.auth.manage seed-demo', language='bash')
            st.caption('Set RELINK_DEMO_PASSWORD in .env first, or you will be prompted. Passwords are stored only '
                       'as salted hashes in .relink/users.json, which is git-ignored.')
        else:
            with st.form('login_form', border=False):
                st.text_input('Username', key='login_username', autocomplete='username', placeholder='e.g. coordinator')
                st.text_input('Password', key='login_password', type='password', autocomplete='current-password')
                st.form_submit_button('Sign in', type='primary', on_click=_sign_in, args=(store,), width='stretch')
            if st.session_state.get('login_error'):
                st.error(st.session_state['login_error'])
            st.caption('Demo-grade sign-in: local hashed passwords, lockout after 5 failures. No SSO or MFA.')
    st.html('<div class="relink-login-roles"><div class="relink-section">Who does what</div><div class="relink-roles">' +
            ''.join(f'<div class="relink-role"><b>{escape(role["label"])}</b><span>{escape(role["summary"])}</span></div>'
                    for role in ROLES.values()) + '</div></div>')


def render_identity(user):
    initials = ''.join(part[0] for part in user.display_name.split()[:2]).upper() or '?'
    st.html(f'<div class="relink-user"><div class="relink-avatar">{escape(initials)}</div><div>'
            f'<b>{escape(user.display_name)}</b><span>{escape(user.role_label)} · {escape(user.username)}</span></div></div>')
    st.button('Sign out', key='sign_out', on_click=sign_out, width='stretch', icon=':material/logout:')


def render_roles_panel(user, root):
    with st.container(border=True):
        st.subheader('Users and roles')
        st.write('Your role: ' + user.role_label)
        matrix = [{'Permission': text, **{r['label']: '✓' if p in r['permissions'] else '' for r in ROLES.values()}}
                  for p, text in PERMISSIONS.items()]
        st.dataframe(matrix, hide_index=True, width='stretch')
        st.caption('Separation of duties: the role that prepares plans cannot approve them, and the administrator '
                   'has no planning or approval authority. Checks run in the service layer, not only in the UI.')
        if can(user, 'manage_users'):
            store = UserStore(default_store_path(root))
            st.dataframe([{'Username': u.username, 'Name': u.display_name, 'Role': u.role_label}
                          for u in store.users()], hide_index=True, width='stretch')
            st.caption('Add users with: python -m project.auth.manage add --username NAME --name "Full name" --role ROLE')

"""Sign-in screen, signed-in identity and the roles panel."""
from html import escape
from pathlib import Path

import streamlit as st

from project.auth import PERMISSIONS, ROLES, AuthError, User, UserStore, can, default_store_path
from project.auth.roles import roles_for


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


FEATURES = (
    ('◉', 'Agents that check each other', 'A Field Analyst, Network Checker and Plan Reviewer read the reports and '
     'challenge unclear facts instead of guessing.'),
    ('✦', 'Plans a solver proves feasible', 'CP-SAT turns verified facts into crew routes and timings, then an '
     'independent validator checks every job.'),
    ('✓', 'People stay in control', 'Nothing moves until a Restoration Manager approves. Every decision is '
     'recorded with who made it and why.'),
    ('▤', 'Results you can measure', 'A separate simulator replays the incident and compares the plan with a '
     'no-AI baseline.'),
)


def render_login(root, brand=''):
    store = UserStore(default_store_path(root))
    st.html('<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],'
            '[data-testid="stExpandSidebarButton"]{display:none}</style>')
    left, right = st.columns([1.25, 1], gap='large', vertical_alignment='center')
    with left:
        st.html('<div class="relink-hero relink-login-hero">' + brand +
                '<div class="relink-eyebrow" style="margin-top:1.2rem">Telecom outage recovery</div>'
                '<h1>Bring the network back <em>faster</em>, together.</h1>'
                '<p>RE:L!NK turns messy field reports into a checked, approved crew plan, and shows '
                'how much downtime it saves.</p>'
                '<div class="relink-features">' +
                ''.join(f'<div class="relink-feature"><i>{icon}</i><div><b>{escape(title)}</b>'
                        f'<span>{escape(text)}</span></div></div>' for icon, title, text in FEATURES) +
                '</div></div>')
    with right, st.container(border=True):
        st.html('<div class="relink-eyebrow">Secure workspace</div>')
        st.subheader('Sign in')
        if not store.exists():
            st.warning('No users are configured on this machine yet.')
            st.write('Create demo users (one per role) from the repository root:')
            st.code('python -m project.auth.manage seed-demo', language='bash')
            st.caption('Set RELINK_DEMO_PASSWORD in .env first, or you will be prompted. Passwords are stored only '
                       'as salted hashes in .relink/users.json, which is git-ignored.')
            return
        with st.form('login_form', border=False):
            st.text_input('Username', key='login_username', autocomplete='username', placeholder='e.g. coordinator')
            st.text_input('Password', key='login_password', type='password', autocomplete='current-password')
            st.form_submit_button('Sign in', type='primary', on_click=_sign_in, args=(store,), width='stretch')
        if st.session_state.get('login_error'):
            st.error(st.session_state['login_error'])
        st.html('<div class="relink-rule"></div><div class="relink-eyebrow">Who does what</div><div class="relink-roles">' +
                ''.join(f'<div class="relink-role"><b>{escape(role["label"])}</b><span>{escape(role["summary"])}</span></div>'
                        for role in ROLES.values()) + '</div>')
        st.caption('Demo-grade sign-in for the MVP: local hashed passwords and lockout after 5 failures. '
                   'Not production identity (no SSO or MFA).')
    st.html('<div class="relink-footer">HyperReAIlity · SLIIT &nbsp; / &nbsp; AI Catalyst 2026'
            ' &nbsp; / &nbsp; Synthetic decision-support workspace</div>')


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

"""Sign-in and role-based access with production roles (no test super-user)."""
import json

import pytest
from streamlit.testing.v1 import AppTest

from project.auth import AuthError, PermissionDenied, User, UserStore, can, default_store_path
from project.auth import manage
from project.auth.roles import PERMISSIONS, ROLES
from project.ui.confirmation_service import confirm_fact, confirmation_binding
from project.ui.planning_service import prepare_plan
from project.ui.review_service import record_decision, review_context
from project.ui.session import DashboardSession, SESSION_KEY
from test_review import choice, prepared, ui_root  # noqa: F401  (fixtures)

pytestmark = pytest.mark.real_roles
COORDINATOR = User('coord', 'Coordinator One', 'noc_coordinator')
MANAGER = User('mgr', 'Manager One', 'restoration_manager')
FIELD = User('field', 'Field One', 'field_supervisor')
AUDITOR = User('audit', 'Auditor One', 'auditor')
ADMIN = User('admin', 'Admin One', 'admin')
PASSWORD = 'correct horse battery'


def test_role_matrix_separates_duties():
    assert can(COORDINATOR, 'generate_plan') and not can(COORDINATOR, 'approve_plan')
    assert can(MANAGER, 'approve_plan') and not can(MANAGER, 'generate_plan')
    assert can(FIELD, 'confirm_fact') and not can(FIELD, 'generate_plan') and not can(FIELD, 'approve_plan')
    assert not any(can(AUDITOR, p) for p in ('generate_plan', 'approve_plan', 'confirm_fact', 'simulate'))
    assert not any(can(ADMIN, p) for p in ('generate_plan', 'approve_plan', 'simulate'))
    assert not can(None, 'view_incident')
    holders = [r for r in ROLES.values() if 'approve_plan' in r['permissions']]
    assert not any('generate_plan' in r['permissions'] for r in holders)
    assert set().union(*(r['permissions'] for r in ROLES.values())) <= set(PERMISSIONS)


def test_store_hashes_passwords_authenticates_and_locks_out(tmp_path):
    store = UserStore(tmp_path / 'users.json')
    store.add_user('Coord', 'Coordinator One', 'noc_coordinator', PASSWORD)
    raw = (tmp_path / 'users.json').read_text()
    assert PASSWORD not in raw and json.loads(raw)['users']['coord']['iterations'] >= 200_000
    assert store.authenticate('coord', PASSWORD) == COORDINATOR
    with pytest.raises(AuthError, match='Incorrect'):
        store.authenticate('nobody', PASSWORD)
    for _ in range(5):
        with pytest.raises(AuthError, match='Incorrect'):
            store.authenticate('coord', 'wrong password', now=1000.0)
    with pytest.raises(AuthError, match='Too many'):
        store.authenticate('coord', PASSWORD, now=1010.0)
    assert store.authenticate('coord', PASSWORD, now=1100.0) == COORDINATOR
    with pytest.raises(AuthError):
        store.add_user('coord', 'Again', 'auditor', PASSWORD)
    with pytest.raises(AuthError):
        store.add_user('weak', 'Weak', 'auditor', 'short')


def test_seed_demo_creates_one_user_per_role_without_printing_password(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('RELINK_DEMO_PASSWORD', PASSWORD)
    assert manage.main(['--store', str(tmp_path / 'u.json'), 'seed-demo']) == 0
    assert PASSWORD not in capsys.readouterr().out
    assert {u.role for u in UserStore(tmp_path / 'u.json').users()} == set(ROLES)


def test_services_enforce_roles_not_just_buttons(choice, ui_root, prepared):
    session = DashboardSession()
    session.select(choice)
    with pytest.raises(PermissionDenied, match='Required role: NOC Coordinator'):
        prepare_plan(session, choice, 'template', 'cp_sat', ui_root, user=MANAGER)
    binding = review_context(prepared, choice)[1]
    with pytest.raises(PermissionDenied):
        record_decision(prepared, choice, binding, 'approve', COORDINATOR.label, '', ui_root, user=COORDINATOR)
    with pytest.raises(Exception, match='signed-in identity'):
        record_decision(prepared, choice, binding, 'approve', 'Someone else', '', ui_root, user=MANAGER)
    assert record_decision(prepared, choice, binding, 'approve', MANAGER.label, 'ok', ui_root, user=MANAGER) == 'approve'
    record = prepared.last_decision
    assert record.authenticated and record.username == 'mgr' and record.role == 'restoration_manager'
    assert record.approval.operator_id == MANAGER.label
    with pytest.raises(PermissionDenied):
        confirm_fact(prepared, choice, confirmation_binding(prepared, choice), 'site', 'S01', 'equipment_ok', False,
                     AUDITOR.label, 'source', 'note', True, ui_root, user=AUDITOR)


def _app(root, monkeypatch, user=None):
    monkeypatch.setenv('RELINK_AUTH_TEST_ROOT', str(root))
    at = AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_AUTH_TEST_ROOT'])",
                             default_timeout=20)
    if user is not None:
        at.session_state['auth_user'] = user
    return at.run()


def test_signed_out_user_sees_setup_or_login_and_no_workspace(ui_root, monkeypatch):
    at = _app(ui_root, monkeypatch)
    assert not at.exception and any('No users are configured' in w.value for w in at.warning)
    assert not at.radio  # no workspace navigation
    UserStore(default_store_path(ui_root)).add_user('mgr', 'Manager One', 'restoration_manager', PASSWORD)
    at = _app(ui_root, monkeypatch)
    at.text_input(key='login_username').input('mgr')
    at.text_input(key='login_password').input('wrong password')
    at.button[0].click().run()
    assert any('Incorrect' in e.value for e in at.error) and 'auth_user' not in at.session_state
    at.text_input(key='login_username').input('mgr')
    at.text_input(key='login_password').input(PASSWORD)
    at.button[0].click().run()
    assert at.session_state['auth_user'] == MANAGER and at.radio(key='workspace_page')


def test_ui_disables_actions_by_role(ui_root, monkeypatch):
    at = _app(ui_root, monkeypatch, MANAGER)
    at.radio(key='workspace_page').set_value('Planning').run()
    assert not at.exception and at.button(key='generate_plan').disabled
    at = _app(ui_root, monkeypatch, COORDINATOR)
    at.radio(key='workspace_page').set_value('Planning').run()
    assert not at.button(key='generate_plan').disabled
    at.button(key='generate_plan').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].core.current is not None
    assert at.button(key='approve_plan').disabled and at.button(key='reject_plan').disabled
    assert any('Restoration Manager' in i.value for i in at.info)
    # Hand-over: the manager signs in to the same browser session and approves.
    at.session_state['auth_user'] = MANAGER
    at.run()
    assert not at.button(key='approve_plan').disabled
    at.button(key='approve_plan').click().run()
    approval = at.session_state[SESSION_KEY].core.approval
    assert not at.exception and approval.decision == 'approve' and approval.operator_id == MANAGER.label

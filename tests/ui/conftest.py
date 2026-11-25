"""UI test sign-in.

Most UI tests check navigation, reruns, binding and audit plumbing across a whole
flow. They run as a test-only identity holding every permission. Real role
separation is covered by tests/ui/test_auth_roles.py with production roles.
"""
import pytest
from streamlit.testing.v1 import AppTest

from project.auth import ROLES, User
from project.auth.roles import PERMISSIONS

TEST_ROLE = 'test_all_permissions'


@pytest.fixture(autouse=True)
def signed_in_test_operator(request, monkeypatch):
    if request.node.get_closest_marker('real_roles'):
        yield
        return
    monkeypatch.setitem(ROLES, TEST_ROLE, {'label': 'Test (all permissions)', 'summary': 'test only',
                                           'permissions': set(PERMISSIONS)})
    original = AppTest.run

    def run(self, *args, **kwargs):
        if 'auth_user' not in self.session_state:
            self.session_state['auth_user'] = User('tester', 'Test operator', TEST_ROLE)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(AppTest, 'run', run)
    yield


def pytest_configure(config):
    config.addinivalue_line('markers', 'real_roles: run the UI with production roles only')

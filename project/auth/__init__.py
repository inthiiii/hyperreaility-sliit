"""Demo-grade sign-in and role-based access for the RE:L!NK workspace.

Passwords are stored only as salted PBKDF2-SHA256 hashes in a local, git-ignored
users file. This is not production identity (no SSO, MFA or central audit); it
makes approval authority and separation of duties real for the MVP.
"""
from project.auth.roles import PERMISSIONS, ROLES, PermissionDenied, User, can, require
from project.auth.store import AuthError, UserStore, default_store_path

__all__ = ['PERMISSIONS', 'ROLES', 'PermissionDenied', 'User', 'can', 'require', 'AuthError', 'UserStore',
           'default_store_path']

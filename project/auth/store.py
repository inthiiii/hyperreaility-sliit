"""Local user store with salted PBKDF2-SHA256 hashes and simple lockout."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

from project.auth.roles import ROLES, User

ITERATIONS = 240_000
MAX_FAILURES = 5
LOCK_SECONDS = 60
USERNAME_CHARS = set('abcdefghijklmnopqrstuvwxyz0123456789._-')


class AuthError(ValueError):
    pass


def default_store_path(root):
    return Path(root) / '.relink' / 'users.json'


def _hash(password, salt, iterations=ITERATIONS):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), iterations).hex()


class UserStore:
    _failures: dict = {}
    _lock = threading.Lock()

    def __init__(self, path):
        self.path = Path(path)

    def exists(self):
        return self.path.is_file()

    def _read(self):
        if not self.exists():
            return {}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('users'), dict):
            raise AuthError('Users file is malformed')
        return data['users']

    def _write(self, users):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'format': 1, 'users': users}, indent=2, sort_keys=True), encoding='utf-8')
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def users(self):
        return [User(name, record['display_name'], record['role']) for name, record in sorted(self._read().items())]

    def add_user(self, username, display_name, role, password, *, replace=False):
        username = username.strip().lower()
        if not 3 <= len(username) <= 32 or not set(username) <= USERNAME_CHARS:
            raise AuthError('Username must be 3-32 characters: a-z, 0-9, dot, underscore or dash')
        if role not in ROLES:
            raise AuthError(f'Unknown role {role}')
        if not 1 <= len(display_name.strip()) <= 60:
            raise AuthError('Display name must be 1-60 characters')
        if len(password) < 10:
            raise AuthError('Password must be at least 10 characters')
        users = self._read()
        if username in users and not replace:
            raise AuthError(f'User {username} already exists')
        salt = secrets.token_hex(16)
        users[username] = {'display_name': display_name.strip(), 'role': role, 'salt': salt,
                           'iterations': ITERATIONS, 'hash': _hash(password, salt)}
        self._write(users)
        return User(username, display_name.strip(), role)

    def authenticate(self, username, password, *, now=None):
        now = time.monotonic() if now is None else now
        username = (username or '').strip().lower()
        with self._lock:
            failures, locked_until = self._failures.get(username, (0, 0.0))
            if locked_until > now:
                raise AuthError(f'Too many failed attempts. Try again in {int(locked_until - now) + 1} s.')
        record = self._read().get(username)
        # Hash even for unknown users so response time does not reveal which usernames exist.
        salt = record['salt'] if record else '00' * 16
        iterations = record['iterations'] if record else ITERATIONS
        ok = hmac.compare_digest(_hash(password or '', salt, iterations), record['hash'] if record else '0' * 64)
        with self._lock:
            if not (record and ok):
                failures += 1
                self._failures[username] = (failures, now + LOCK_SECONDS if failures >= MAX_FAILURES else 0.0)
                raise AuthError('Incorrect username or password')
            self._failures.pop(username, None)
        return User(username, record['display_name'], record['role'])

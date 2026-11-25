"""Manage local RE:L!NK users.

    python -m project.auth.manage seed-demo     # one demo user per role
    python -m project.auth.manage add --username kiru --name "Kiruthika" --role auditor
    python -m project.auth.manage list

Passwords are read from RELINK_DEMO_PASSWORD (seed-demo) or prompted without echo.
They are never printed, logged or committed; .relink/ is git-ignored.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

from project.auth.roles import ROLES
from project.auth.store import AuthError, UserStore, default_store_path

ROOT = Path(__file__).resolve().parents[2]
DEMO_USERS = [('coordinator', 'Demo NOC Coordinator', 'noc_coordinator'),
              ('manager', 'Demo Restoration Manager', 'restoration_manager'),
              ('field', 'Demo Field Supervisor', 'field_supervisor'),
              ('auditor', 'Demo Auditor', 'auditor'),
              ('admin', 'Demo Administrator', 'admin')]


def _password(prompt):
    first = getpass.getpass(prompt)
    if getpass.getpass('Repeat: ') != first:
        raise AuthError('Passwords do not match')
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--store', type=Path, default=default_store_path(ROOT))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('seed-demo', help='Create one demo user per role')
    add = sub.add_parser('add', help='Add or replace a user')
    add.add_argument('--username', required=True)
    add.add_argument('--name', required=True)
    add.add_argument('--role', required=True, choices=sorted(ROLES))
    add.add_argument('--replace', action='store_true')
    sub.add_parser('list', help='List users and roles (no hashes)')
    args = parser.parse_args(argv)
    store = UserStore(args.store)
    try:
        if args.command == 'list':
            for user in store.users():
                print(f'{user.username:14} {user.role_label:20} {user.display_name}')
        elif args.command == 'add':
            store.add_user(args.username, args.name, args.role, _password(f'Password for {args.username}: '),
                           replace=args.replace)
            print(f'Saved {args.username} ({ROLES[args.role]["label"]}) to {args.store}')
        else:
            from dotenv import load_dotenv
            load_dotenv(ROOT / '.env', override=False)
            password = os.environ.get('RELINK_DEMO_PASSWORD') or _password('Shared demo password: ')
            for username, name, role in DEMO_USERS:
                store.add_user(username, name, role, password, replace=True)
            print('Created demo users: ' + ', '.join(u for u, *_ in DEMO_USERS) + f' in {args.store}')
    except AuthError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

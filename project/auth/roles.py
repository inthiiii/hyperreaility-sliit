"""Roles, permissions and the checks used by service functions."""
from __future__ import annotations

from dataclasses import dataclass

PERMISSIONS = {
    'view_incident': 'Inspect incidents, plans and evidence',
    'generate_plan': 'Run the planning workflow (template, single or multi agent)',
    'confirm_fact': 'Record an operator clarification or field update (creates new evidence)',
    'approve_plan': 'Approve a validated plan for simulation',
    'reject_plan': 'Reject a plan',
    'decide_priority': 'Accept or reject agent priority proposals',
    'simulate': 'Run the approved plan in the simulator',
    'continue_incident': 'Accept a simulator checkpoint and continue the incident',
    'view_history': 'Read recorded runs, decisions and traces',
    'export_records': 'Download recorded runs and decisions',
    'view_settings': 'See model, budget and access settings',
    'manage_users': 'See users and roles',
}

ROLES = {
    'noc_coordinator': {
        'label': 'NOC Coordinator',
        'summary': 'Prepares plans and answers agent questions. Cannot approve.',
        'permissions': {'view_incident', 'generate_plan', 'confirm_fact', 'view_history', 'export_records'},
    },
    'restoration_manager': {
        'label': 'Restoration Manager',
        'summary': 'Approves or rejects plans and priority proposals, runs and continues simulation.',
        'permissions': {'view_incident', 'approve_plan', 'reject_plan', 'decide_priority', 'simulate',
                        'continue_incident', 'view_history', 'export_records'},
    },
    'field_supervisor': {
        'label': 'Field Supervisor',
        'summary': 'Sees assigned work and submits field updates, which expire approval and trigger replanning.',
        'permissions': {'view_incident', 'confirm_fact'},
    },
    'auditor': {
        'label': 'Auditor',
        'summary': 'Read-only access to incidents, history and traces.',
        'permissions': {'view_incident', 'view_history', 'export_records'},
    },
    'admin': {
        'label': 'Administrator',
        'summary': 'Settings and users. Deliberately has no planning or approval authority.',
        'permissions': {'view_incident', 'view_history', 'view_settings', 'manage_users'},
    },
}


class PermissionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    role: str

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f'Unknown role {self.role}')

    @property
    def role_label(self):
        return ROLES[self.role]['label']

    @property
    def label(self):
        """Identity written into decisions, approvals and attempt records."""
        return f'{self.display_name} ({self.username} · {self.role_label})'


def can(user, permission):
    if permission not in PERMISSIONS:
        raise ValueError(f'Unknown permission {permission}')
    return isinstance(user, User) and permission in ROLES[user.role]['permissions']


def require(user, permission):
    if not can(user, permission):
        who = user.role_label if isinstance(user, User) else 'Signed-out user'
        holders = ', '.join(r['label'] for r in ROLES.values() if permission in r['permissions'])
        raise PermissionDenied(f'{who} cannot {PERMISSIONS[permission].lower()}. Required role: {holders}.')
    return user


def roles_for(permission):
    return [r['label'] for r in ROLES.values() if permission in r['permissions']]

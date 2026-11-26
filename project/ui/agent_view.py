"""Readable projections of a run: crew Gantt rows, agent conversation, operator inbox.

Pure functions over a RunResult. They summarise recorded messages; they never
call a model or change state.
"""
from __future__ import annotations

ROLE_NAMES = {
    'network_investigator': 'Network Investigator', 'field_resource_planner': 'Field Resource Planner',
    'service_priority_assessor': 'Service Priority Assessor', 'plan_reviewer': 'Plan Reviewer',
    'single_agent': 'Single agent', 'coordinator': 'Coordinator', 'deterministic_scheduler': 'CP-SAT scheduler',
    'rejected_agent_output': 'Audit', 'audit': 'Audit', 'template_baseline': 'Template parser',
    'review_audit': 'Audit',
}
KIND_ORDER = ['Extraction', 'Shared facts', 'Specialist finding', 'Hold applied', 'Schedule',
              'Review', 'Challenge', 'Rejected output', 'Other']


def name(role):
    return ROLE_NAMES.get(role, role.replace('_', ' ').title())


def gantt_rows(result):
    """One lane per crew (travel + work) plus the generator's powered window."""
    if result.plan is None:
        return []
    s = result.state.scenario
    gens = {g.generator_id: g for g in s.generators}
    rows = []
    for a in result.plan.actions:
        label = f'{a.action_id} → {a.target_id}'
        if a.work_start_min > a.departure_min:
            rows.append({'Lane': f'Crew {a.crew_id}', 'Stage': 'Travel', 'Start': a.departure_min,
                         'End': a.work_start_min, 'Action': label})
        rows.append({'Lane': f'Crew {a.crew_id}', 'Stage': 'Work', 'Start': a.work_start_min,
                     'End': a.work_end_min, 'Action': label})
        if a.kind == 'generator_deploy' and a.generator_id in gens:
            end = min(s.horizon_min, a.work_end_min + gens[a.generator_id].autonomy_minutes)
            rows.append({'Lane': f'Generator {a.generator_id}', 'Stage': 'Powering site', 'Start': a.work_end_min,
                         'End': end, 'Action': f'{a.generator_id} at {a.target_id} (fuel runs out at {end})'})
    for g in s.active_generators:
        rows.append({'Lane': f'Generator {g.generator_id}', 'Stage': 'Powering site', 'Start': s.current_time_min,
                     'End': min(s.horizon_min, g.expires_at_min), 'Action': f'{g.generator_id} already at {g.site_id}'})
    return rows


def _summary(message):
    sender, content = message.get('sender', ''), message.get('finding') or {}
    if not isinstance(content, dict):
        return 'Other', str(content)[:200]
    if sender == 'deterministic_scheduler':
        actions = content.get('actions', [])
        return 'Schedule', f'{len(actions)} actions: ' + ', '.join(a['action_id'] for a in actions[:6]) + ('…' if len(actions) > 6 else '')
    if sender == 'rejected_agent_output':
        return 'Rejected output', content.get('validation_error', 'rejected')
    if 'rejected_fact' in content:
        item = content['rejected_fact']
        return 'Rejected output', f"Dropped fact {item['fact'].get('target_id')}.{item['fact'].get('attribute')}: {item['reason']}"
    if content.get('shared') == 'facts':
        return 'Shared facts', f"{content.get('fact_count', 0)} facts; ignored reports {', '.join(content.get('ignored_report_ids', [])) or 'none'}"
    if 'fact_challenges' in content and message.get('recipient') in ('network_investigator', 'single_agent'):
        return 'Challenge', '; '.join(f"{c['report_id']} {c['target_id']}.{c['attribute']}: {c['problem']}" for c in content['fact_challenges'])
    if 'applied_action_ids' in content:
        return 'Hold applied', f"Held {', '.join(content['applied_action_ids'])}: {content['request']['reason']}"
    if 'decision' in content:
        challenges = content.get('fact_challenges', [])
        text = f"Decision: {content['decision']}"
        if challenges:
            text += f' · {len(challenges)} fact challenge(s)'
        if content.get('findings'):
            text += ' · ' + ' | '.join(content['findings'])
        return 'Review', text
    if 'facts' in content:
        ignored = content.get('ignored_reports', [])
        flagged = [i['report_id'] for i in ignored if i.get('kind') == 'instruction_attempt']
        text = f"{len(content['facts'])} facts extracted, {len(ignored)} reports ignored"
        if flagged:
            text += f" (instruction attempt flagged: {', '.join(flagged)})"
        return 'Extraction', text
    if 'finding' in content:
        extra = []
        if content.get('requests'):
            extra.append(f"{len(content['requests'])} hold request(s)")
        if content.get('questions'):
            extra.append(f"{len(content['questions'])} question(s)")
        if content.get('priority_proposals'):
            extra.append(f"{len(content['priority_proposals'])} priority proposal(s)")
        return 'Specialist finding', content['finding'][:240] + (f" · {', '.join(extra)}" if extra else '')
    return 'Other', ', '.join(sorted(content))[:200]


def conversation_rows(result):
    rows = []
    for index, message in enumerate(result.messages, 1):
        kind, text = _summary(message)
        rows.append({'Step': index, 'From': name(message.get('sender', '?')),
                     'To': name(message.get('recipient', 'coordinator')), 'Kind': kind,
                     'State': message.get('state_version'), 'Summary': text})
    return rows


def collaboration_counts(result):
    rows = conversation_rows(result)
    agents = {r['From'] for r in rows if r['From'] in ROLE_NAMES.values()} - {'Coordinator', 'CP-SAT scheduler', 'Audit', 'Template parser'}
    return {'agents': len(agents), 'messages': len(rows),
            'challenges': sum(r['Kind'] == 'Challenge' for r in rows),
            'holds': sum(r['Kind'] == 'Hold applied' for r in rows),
            'schedules': sum(r['Kind'] == 'Schedule' for r in rows),
            'rejected': sum(r['Kind'] == 'Rejected output' for r in rows)}


UNKNOWN_TEXT = {'equipment_ok': 'is the equipment working', 'grid_power_ok': 'is grid power on',
                'backhaul_ok': 'is the backhaul link working', 'open': 'is the road open'}


def unknown_questions(result, asked=()):
    """Facts the run could not establish, phrased as operator questions (one per fact)."""
    out = []
    for item in result.state.unresolved_facts:
        parts = item.split(':')
        typ, target = parts[0], parts[1]
        attribute = parts[2] if len(parts) > 2 else {'link': 'backhaul_ok', 'road': 'open'}.get(typ)
        if attribute is None or target in asked:
            continue
        out.append({'target_id': target, 'question': f'Not established from the reports: {UNKNOWN_TEXT[attribute]} '
                                                     f'at {target}?', 'source': 'evidence_check',
                    'evidence_ids': [], 'fact': f'{typ}:{target}:{attribute}'})
    return out


def inbox(result):
    meta = result.metadata or {}
    asked = list(meta.get('operator_questions', []))
    return {'questions': asked + unknown_questions(result, {q.get('target_id') for q in asked}),
            'proposals': list(meta.get('priority_proposals', [])),
            'ignored': list(meta.get('ignored_reports', []))}


STAGE_TEXT = {'investigate': 'reading the incident reports', 'reinvestigate': 're-checking challenged facts',
              'resources': 'checking crews, roads and the generator', 'priorities': 'weighing service priorities',
              'review': 'independently reviewing the plan', 'analyse': 'analysing everything in one context',
              'reanalyse': 're-analysing after its self-review',
              'schedule': 'building the schedule (software, not AI)'}
ICONS = {'Extraction': '🔎', 'Shared facts': '📨', 'Specialist finding': '🧭', 'Hold applied': '⏸️',
         'Schedule': '🗓️', 'Review': '✅', 'Challenge': '⚠️', 'Rejected output': '🚫', 'Other': '•'}


def feed_line(message):
    """(markdown line, status label or None) for one live orchestrator message."""
    if message.get('recipient') == 'working':
        who = name(message['sender'])
        return f'⏳ **{who}** is {STAGE_TEXT.get(message.get("stage"), "working")}…', f'{who} is working…'
    kind, text = _summary(message)
    return (f'{ICONS.get(kind, "•")} **{name(message.get("sender", "?"))}** → '
            f'{name(message.get("recipient", "coordinator"))}: {text}'), None


class LiveFeed:
    """Display-only observer: turns live orchestrator messages into short status lines."""

    def __init__(self, status):
        self.status = status
        self.count = 0

    @staticmethod
    def line(message):
        return feed_line(message)

    def __call__(self, message):
        text, label = self.line(message)
        if label:
            self.status.update(label=label)
        else:
            self.count += 1
        self.status.markdown(text)

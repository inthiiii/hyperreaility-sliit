"""One-page plan summary (PDF): jobs, reasons, approval and measured result.

Built only from recorded objects (run, decision, simulation). Never calls a model,
never reads hidden truth and never changes session state.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from project.ui.agent_view import name

MODE = {'template': 'Offline template baseline', 'single': 'Hosted single agent', 'multi': 'Hosted multi-agent workflow'}


def _reasons(result):
    out = []
    for message in result.messages:
        content = message.get('finding') if isinstance(message.get('finding'), dict) else {}
        sender = message.get('sender', '')
        if message.get('recipient') != 'coordinator':
            continue
        if content.get('finding') and sender not in ('deterministic_scheduler',):
            out.append((name(sender), str(content['finding'])[:400]))
        if 'decision' in content:
            text = f"Decision: {content['decision']}"
            if content.get('findings'):
                text += ' · ' + ' | '.join(map(str, content['findings']))[:300]
            out.append((name(sender), text))
    for effect in (result.metadata or {}).get('decision_effects', []):
        out.append(('Hold applied', f"{', '.join(effect['applied_action_ids'])}: {effect['request']['reason']}"[:300]))
    return out


def build_summary(result, decision=None, simulation=None, comparison=None):
    """Plain dict so the summary can be tested and rendered as PDF or text."""
    scenario = result.state.scenario
    names = {s.site_id: s.label for s in scenario.sites}
    plan = result.plan
    jobs = [{'crew': a.crew_id, 'job': a.action_id, 'what': a.kind.replace('_', ' '),
             'where': f'{names.get(a.target_id, a.target_id)} ({a.target_id})', 'leave': a.departure_min,
             'work': f'{a.work_start_min}–{a.work_end_min}'}
            for a in sorted(plan.actions if plan else [], key=lambda x: (x.crew_id, x.departure_min))]
    meta = result.metadata or {}
    summary = {
        'title': f'Recovery plan · {scenario.scenario_id}',
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'facts': [('Incident', f'{scenario.scenario_id} · {scenario.region_label}'),
                  ('Run', result.run_id), ('Plan', plan.plan_id if plan else 'none'),
                  ('Mode', MODE.get(result.mode, result.mode)), ('Status', result.status.replace('_', ' ')),
                  ('State version', str(result.state.state_version)),
                  ('Model calls', str(len(result.model_usage)))],
        'jobs': jobs,
        'reasons': _reasons(result),
        'unmet': list(plan.unmet_needs) if plan else [],
        'questions': [f"{q.get('target_id')}: {q.get('question')}" for q in meta.get('operator_questions', [])],
        'flagged': [f"{i['report_id']} ({i['kind'].replace('_', ' ')})" for i in meta.get('ignored_reports', [])
                    if i.get('kind') == 'instruction_attempt'],
        'approval': None, 'result': None, 'comparison': None,
    }
    if decision is not None:
        approval = decision.approval if hasattr(decision, 'approval') else decision
        summary['approval'] = [('Decision', approval.decision), ('By', approval.operator_id),
                               ('At', approval.timestamp.strftime('%Y-%m-%d %H:%M UTC')),
                               ('Plan hash', approval.plan_hash[:16])]
        note = getattr(decision, 'note', '')
        if note:
            summary['approval'].append(('Note', note))
    if simulation is not None:
        m = simulation.metrics
        scope = simulation.run_metadata.get('measurement_scope', '')
        rows = [('Scope', 'whole incident' if scope == 'complete_incident' else scope.replace('_', ' ') or 'recorded')]
        for key, label in (('weighted_downtime_min', 'Weighted downtime (service-min)'),
                           ('critical_service_downtime_min', 'Critical service downtime (min)'),
                           ('first_restoration_min', 'First restoration (minute)'),
                           ('services_available_at_horizon_end', 'Services up at the end'),
                           ('actions_completed', 'Actions completed')):
            if m.get(key) is not None:
                rows.append((label, f'{m[key]:,.0f}' if isinstance(m[key], (int, float)) else str(m[key])))
        summary['result'] = rows
    if comparison and 'weighted_downtime_min' in comparison and simulation is not None:
        ai = simulation.metrics.get('weighted_downtime_min')
        base = comparison['weighted_downtime_min']
        if ai is not None:
            summary['comparison'] = [('With RE:L!NK', f'{ai:,.0f}'), ('CP-SAT without AI', f'{base:,.0f}'),
                                     ('Difference', f'{base - ai:,.0f} ({(base - ai) / base * 100 if base else 0:.1f} % less)')]
    return summary


def pdf_bytes(summary):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ink, accent, soft, grid = (colors.HexColor(c) for c in ('#16202e', '#1f8f78', '#eef5f3', '#b8c4cf'))
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=ss['Title'], fontSize=17, leading=21, textColor=ink, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=ss['Heading2'], fontSize=11.5, leading=14, textColor=accent, spaceBefore=7, spaceAfter=3)
    body = ParagraphStyle('b', parent=ss['Normal'], fontSize=8.6, leading=11, textColor=ink)
    small = ParagraphStyle('s', parent=body, fontSize=7.4, leading=9.5, textColor=colors.HexColor('#4a5a6a'))
    width = A4[0] - 30 * mm

    def p(text, style=body):
        return Paragraph(escape(str(text)), style)

    def table(rows, widths, header=True):
        data = [[p(c) for c in row] for row in rows]
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        style = [('GRID', (0, 0), (-1, -1), 0.4, grid), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                 ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5)]
        if header:
            style.append(('BACKGROUND', (0, 0), (-1, 0), soft))
        t.setStyle(TableStyle(style))
        return t

    def pairs(rows):
        return table([[k, v] for k, v in rows], [width * 0.3, width * 0.7], header=False)

    story = [p('RE:L!NK', ParagraphStyle('brand', parent=body, textColor=accent, fontName='Helvetica-Bold')),
             p(summary['title'], h1), p(f"Generated {summary['generated']} · synthetic decision-support record", small),
             Spacer(1, 4), pairs(summary['facts']), p('Crew jobs', h2)]
    if summary['jobs']:
        story.append(table([['Crew', 'Job', 'What', 'Where', 'Leave', 'Work (min)']] +
                           [[j['crew'], j['job'], j['what'], j['where'], j['leave'], j['work']] for j in summary['jobs']],
                           [width * f for f in (0.08, 0.17, 0.2, 0.3, 0.1, 0.15)]))
    else:
        story.append(p('No crew jobs in this plan.'))
    story.append(p('Why: agent findings and review', h2))
    story.append(table([['From', 'Finding']] + [[a, b] for a, b in summary['reasons'][:10]], [width * 0.22, width * 0.78])
                 if summary['reasons'] else p('No agent findings were recorded (template or no-AI run).'))
    extras = [('Unmet needs', '; '.join(summary['unmet'])), ('Open questions', '; '.join(summary['questions'])),
              ('Instruction attempts flagged', ', '.join(summary['flagged']))]
    extras = [(k, v) for k, v in extras if v]
    if extras:
        story += [Spacer(1, 4), pairs(extras)]
    story.append(p('Approval', h2))
    story.append(pairs(summary['approval']) if summary['approval'] else p('Not yet approved.'))
    story.append(p('Measured result (independent simulator)', h2))
    story.append(pairs(summary['result']) if summary['result'] else p('Not simulated yet.'))
    if summary['comparison']:
        story += [p('Compared with the no-AI baseline (same incident)', h2), pairs(summary['comparison'])]
    story += [Spacer(1, 6), p('Synthetic incident. Planned actions are simulated only; nothing is dispatched to real crews. '
                              'Agent findings are model outputs checked by the validator and the operator, not verified facts.', small)]
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm,
                      bottomMargin=12 * mm, title=summary['title'], author='RE:L!NK').build(story)
    return buffer.getvalue()


def text_summary(summary):
    """Plain-text version for quick copy/paste."""
    lines = [summary['title'], *(f'{k}: {v}' for k, v in summary['facts']), '', 'Jobs:']
    lines += [f"  {j['crew']} {j['job']} — {j['what']} at {j['where']}, leave {j['leave']}, work {j['work']}"
              for j in summary['jobs']] or ['  none']
    for title, rows in (('Approval', summary['approval']), ('Measured result', summary['result']),
                        ('No-AI comparison', summary['comparison'])):
        if rows:
            lines += ['', title + ':', *(f'  {k}: {v}' for k, v in rows)]
    return '\n'.join(lines)


def render_plan_export(session, choice):
    """Download the current plan as a one-page PDF (Results page)."""
    import streamlit as st

    from project.auth import can
    from project.ui.auth_view import current_user, needs_role
    result = session.core.current
    st.subheader('Plan summary')
    if result is None or result.plan is None or result.state.source_hash != choice.content_hash:
        st.info('Generate a plan first. The summary covers jobs, reasons, approval and the measured result.')
        return
    decision = session.last_decision if session.last_decision is not None and \
        session.last_decision.approval.plan_id == result.plan.plan_id else None
    sim = session.simulation_result if session.simulation_result is not None and \
        session.simulation_result.plan_id == result.plan.plan_id else None
    cache = st.session_state.get('no_ai_compare', {})
    comparison = cache.get((choice.key, session.core.approval.plan_hash if session.core.approval else None))
    summary = build_summary(result, decision, sim, comparison)
    allowed = can(current_user(), 'export_records')
    st.caption('One page: crew jobs, the agents\' reasons, the approval and the measured result'
               + (' and the no-AI comparison.' if summary['comparison'] else '.'))
    st.download_button('Download plan summary (PDF)', pdf_bytes(summary) if allowed else b'',
                       file_name=f'relink-plan-{result.state.scenario_id}-{result.plan.plan_id[:8]}.pdf',
                       mime='application/pdf', key='plan_pdf', disabled=not allowed, on_click='ignore',
                       help=None if allowed else needs_role('export_records'))


def history_parts(entry, catalog):
    """(run, decision, simulation) for a saved run record, using only validated linked records."""
    from project.core.coordinator import RunResult
    from project.ui.history_data import linked_simulation, public_payload
    from project.ui.review_service import DecisionRecord
    result = RunResult.model_validate(public_payload(entry.payload))
    decisions = [DecisionRecord.model_validate(item.payload) for item in catalog.entries
                 if item.kind == 'decision' and item.run_id == result.run_id]
    decision = max(decisions, key=lambda d: d.recorded_at_utc) if decisions else None
    simulation = None
    for item in catalog.entries:
        if item.kind == 'simulation' and item.run_id == result.run_id and item.status == 'completed':
            simulation, _ = linked_simulation(item, catalog)
            if simulation is not None:
                break
    return result, decision, simulation

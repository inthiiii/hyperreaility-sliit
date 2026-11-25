"""Explicit operator evidence; never reads evaluator answers or mutates dataset files."""
from project.auth import require
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import Field
from project.agents.extraction import template_facts
from project.core.schemas import Contract, Report, VerifiedState
from project.core.state import digest, build_verified_state
from project.ui.catalog import ScenarioChoice
from project.ui.local_records import save_record
from project.ui.planning_service import begin_new_attempt
from project.ui.review_service import ReviewBlocked, ensure_current_source

PHRASES = {
    ('site','equipment_ok'): ('equipment has failed','equipment is operational'),
    ('site','grid_power_ok'): ('grid power is unavailable','grid power is available'),
    ('link','backhaul_ok'): ('backhaul link has failed','backhaul link is operational'),
    ('road','open'): ('access road is closed','access road is open'),
}


class ConfirmationRecord(Contract):
    confirmation_id: str
    session_id: str
    scenario_id: str
    run_id: str | None
    input_hash_before: str
    input_hash_after: str
    source_hash: str
    request_hash: str
    operator_id: str
    verification_source: str
    note: str
    report: Report
    updated_state: VerifiedState
    recorded_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    authenticated: bool = False
    username: str | None = None
    role: str | None = None


def fact_options(scenario):
    options={}
    for typ, identifiers, attrs in [('site',[s.site_id for s in scenario.sites],['equipment_ok','grid_power_ok']),
                                     ('link',[l.link_id for l in scenario.links],['backhaul_ok']),
                                     ('road',[r.road_id for r in scenario.roads],['open'])]:
        for target in identifiers:
            for attr in attrs:options[f'{typ}:{target}:{attr}']=(typ,target,attr)
    return options


def confirmation_binding(session, choice):
    if session.busy:
        raise ReviewBlocked('Wait for the current operation to finish.')
    if (session.selected_key,session.scenario_hash)!=(choice.key,choice.content_hash) or digest(choice.scenario)!=choice.content_hash:
        raise ReviewBlocked('The displayed incident changed. Refresh before recording clarification.')
    if session.simulation_result is not None:
        raise ReviewBlocked('Accept the paused event update first, or select a new incident after completion.')
    run=session.core.current
    return digest({'input':choice.content_hash,'run':digest(run) if run is not None else None,
                   'next_version':session.core.next_state_version})


def confirm_fact(session, choice, expected_binding, target_type, target_id, attribute, value,
                 operator_id, verification_source, note, acknowledged, root, *, user=None):
    if user is not None:
        require(user, 'confirm_fact')
    if type(value) is not bool or acknowledged is not True:
        raise ReviewBlocked('Choose a boolean value and explicitly acknowledge verification.')
    if not isinstance(operator_id,str) or not 1<=len(operator_id.strip())<=120:
        raise ReviewBlocked('Enter an operator label of 1–120 characters.')
    if not isinstance(verification_source,str) or not 1<=len(verification_source.strip())<=500:
        raise ReviewBlocked('Record a verification source of 1–500 characters.')
    if not isinstance(note,str) or not 1<=len(note.strip())<=2000:
        raise ReviewBlocked('Record the reason and verification details (1–2000 characters).')
    target=(target_type,target_id,attribute)
    if target not in fact_options(choice.scenario).values():
        raise ReviewBlocked('Choose a known visible asset and supported fact.')
    ensure_current_source(session,choice,root)
    request_hash=digest({'binding':expected_binding,'target':target,'value':value,
                         'operator':operator_id.strip(),'source':verification_source.strip(),'note':note.strip()})
    if request_hash in session.confirmation_requests:
        return 'duplicate'
    if confirmation_binding(session,choice)!=expected_binding:
        raise ReviewBlocked('The incident or plan changed after this form was displayed. Review the new state.')
    report_map={r.report_id:r for r in choice.scenario.reports}
    previous=[f.evidence_ids[0] for f in template_facts(choice.scenario)
              if (f.target_type,f.target_id,f.attribute)==target and
              report_map[f.evidence_ids[0]].source_type=='operator_confirmation']
    report=Report(report_id='OP-'+str(uuid4()),source_type='operator_confirmation',
                  observed_at_min=choice.scenario.current_time_min,received_at_min=choice.scenario.current_time_min,
                  text=f'{target_id}: {PHRASES[target_type,attribute][int(value)]}.',supersedes_report_ids=previous)
    scenario=choice.scenario.model_copy(deep=True)
    scenario.reports.append(report)
    # Revalidate the complete new input including explicit correction references.
    scenario=type(scenario).model_validate(scenario.model_dump(mode='python'))
    run=session.core.current
    facts=run.state.facts if run is not None and run.state.source_hash==choice.content_hash else []
    updated=build_verified_state(scenario,facts,state_version=session.core.next_state_version)
    record=ConfirmationRecord(confirmation_id=str(uuid4()),session_id=session.session_id,
        scenario_id=scenario.scenario_id,run_id=run.run_id if run is not None else None,
        input_hash_before=choice.content_hash,input_hash_after=digest(scenario),
        source_hash=session.source_hash or choice.content_hash,request_hash=request_hash,
        operator_id=operator_id.strip(),verification_source=verification_source.strip(),note=note.strip(),
        authenticated=user is not None,username=user.username if user else None,role=user.role if user else None,
        report=report,updated_state=updated)
    # Fail closed: a persistence failure must not leave the earlier approval active.
    session.core.approval=None
    save_record(Path(root)/'results/local_runs/confirmations',record.confirmation_id,record.model_dump(mode='json'))
    begin_new_attempt(session)
    version=session.core.invalidate_for_state_update()
    assert version==updated.state_version
    selected=ScenarioChoice(choice.key,'operator_confirmed',scenario,digest(scenario))
    if session.continuation_choice is not None:
        session.continuation_choice=selected
    else:
        session.confirmation_choice=selected
    session.scenario_hash=selected.content_hash
    session.confirmation_requests.add(request_hash)
    session.confirmation_history.append(record)
    return 'recorded'

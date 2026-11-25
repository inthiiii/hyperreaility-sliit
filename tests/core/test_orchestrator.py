"""Agent orchestrator (relink-agents-v14) with a scripted fake model; no live API."""
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from project.core.coordinator import approve_run
from project.core.orchestrator import AgentOrchestrator, normalize_facts
from project.core.schemas import EvidenceFact
from project.data.evaluator import EvaluatorLoader
from project.data.loader import CaseLoader
from project.evaluation.extraction import truth_extraction_metrics
from project.llm.client import HostedAdapter, RunBudget
from test_models import FakeClient

V3 = Path(__file__).resolve().parents[2] / 'releases' / 'evidence-v3-20261126' / 'data'
LOADER = CaseLoader(V3 / 'processed' / 'agent_inputs')
TRUTH = EvaluatorLoader(V3 / 'evaluation' / 'ground_truth')


def case(cid):
    return LOADER.load_case(LOADER.find(cid))


def adapter(replies, budget=None):
    return HostedAdapter('openai', 'fake-model', 'fake-key', client=FakeClient(replies), budget=budget)


def fact(rid, typ, target, attr, value):
    return {'target_type': typ, 'target_id': target, 'attribute': attr, 'value': value, 'evidence_ids': [rid],
            'observed_at_min': None, 'received_at_min': None, 'status': 'unverified', 'reason': ''}


def perfect_facts(cid):
    return [fact(l['report_id'], l['target_type'], l['target_id'], l['attribute'], l['reported_value'])
            for l in TRUTH.load(cid).expected_report_facts]


def ignored(cid):
    kinds = {'prompt_injection': 'instruction_attempt'}
    return [{'report_id': d['report_id'], 'kind': kinds.get(d['kind'], 'no_operational_claim'), 'note': d['kind']}
            for d in TRUTH.load(cid).distractor_reports]


def extraction(facts, ignored_reports=()):
    return json.dumps({'facts': facts, 'ignored_reports': list(ignored_reports), 'finding': 'Extracted claims'})


def specialist(requests=(), questions=(), proposals=()):
    return json.dumps({'finding': 'Checked', 'evidence_ids': [], 'requests': list(requests),
                       'questions': list(questions), 'priority_proposals': list(proposals)})


def review(decision='approve', challenges=(), requests=()):
    return json.dumps({'decision': decision, 'fact_challenges': list(challenges), 'requests': list(requests),
                       'findings': [] if decision == 'approve' else ['see challenges'], 'evidence_ids': []})


def analysis(facts, ignored_reports=(), requests=(), proposals=()):
    return json.dumps({'facts': facts, 'ignored_reports': list(ignored_reports), 'requests': list(requests),
                       'questions': [], 'priority_proposals': list(proposals), 'finding': 'All jobs done'})


def payloads(a):
    return [json.loads(r['messages'][-1]['content']) for r in a.client.requests]


def test_multi_agent_end_to_end_with_scoped_contexts():
    s = case('DEV-003')
    a = adapter([extraction(perfect_facts('DEV-003'), ignored('DEV-003')), specialist(), specialist(), review()])
    result = AgentOrchestrator(a).run(s, 'multi')
    assert result.status == 'awaiting_approval' and result.validation.valid
    assert result.plan.actions and not result.state.unresolved_facts
    senders = {m['sender'] for m in result.messages}
    assert {'network_investigator', 'field_resource_planner', 'service_priority_assessor', 'plan_reviewer'} <= senders
    sent = payloads(a)
    assert [p['stage'] for p in sent] == ['investigate', 'resources', 'priorities', 'review']
    inv, res, pri, rev = (p['context'] for p in sent)
    assert 'reports' in inv and 'crews_id_location_from_until_skills' not in inv
    assert 'reports' not in res and 'action_catalog' in res and 'investigator_facts' in res
    assert 'services_id_site_critical_weight' in pri
    assert 'reports' in rev and 'extracted_facts' in rev and 'Extracted claims' not in json.dumps(rev)
    shared = [m for m in result.messages if m['sender'] == 'network_investigator' and m['recipient'] != 'coordinator']
    assert {m['recipient'] for m in shared} == {'field_resource_planner', 'service_priority_assessor', 'plan_reviewer'}
    approve_run(result, 'operator')


def test_reviewer_fact_challenge_routes_back_and_changes_plan():
    s = case('DEV-001')
    wrong = [fact('REP-001', 'site', 'S02', 'equipment_ok', False)]  # alias resolved to the wrong site
    challenge = {'report_id': 'REP-001', 'target_id': 'S02', 'attribute': 'equipment_ok',
                 'problem': 'Report names a different site code; resolve via the directory.'}
    a = adapter([extraction(wrong), specialist(), specialist(), review('revise', [challenge]),
                 extraction(perfect_facts('DEV-001')), review()])
    result = AgentOrchestrator(a).run(s, 'multi')
    assert result.status == 'awaiting_approval'
    plans = [m['finding'] for m in result.messages if m['sender'] == 'deterministic_scheduler']
    assert len(plans) == 2
    # A wrong-site claim contradicts the snapshot, so the resolver leaves both sites
    # unknown rather than repairing the wrong one.
    assert plans[0]['actions'] == []
    assert {x['target_id'] for x in plans[1]['actions']} == {'S01'}
    assert result.metadata['fact_challenges'][0]['round'] == 1
    routed = [m for m in result.messages if m['recipient'] == 'network_investigator']
    assert routed and routed[0]['sender'] == 'plan_reviewer'
    assert payloads(a)[4]['stage'] == 'reinvestigate' and 'reviewer_challenges' in payloads(a)[4]['context']
    metrics = truth_extraction_metrics(TRUTH.load('DEV-001'), result.metadata['raw_facts'], result.metadata['final_facts'])
    assert metrics['initial']['f1'] == 0 and metrics['final']['f1'] == 1


def test_conflict_produces_partial_plan_and_operator_question_not_escalation():
    s = case('DEV-006')
    a = adapter([extraction(perfect_facts('DEV-006'), ignored('DEV-006')), specialist(), specialist(), review()])
    result = AgentOrchestrator(a).run(s, 'multi')
    assert result.status == 'awaiting_approval'
    assert result.state.unresolved_facts == ['site:S01:equipment_ok']
    questions = result.metadata['operator_questions']
    assert questions[0]['source'] == 'evidence_resolver' and questions[0]['target_id'] == 'S01'
    assert any('Unresolved evidence' in need for need in result.plan.unmet_needs)


def test_invalid_facts_are_rejected_individually_and_authority_comes_from_source():
    s = case('DEV-007')
    facts = [EvidenceFact(**fact('REP-001', 'site', 'S99', 'equipment_ok', False)),
             EvidenceFact(**fact('REP-001', 'site', 'S01', 'backhaul_ok', False)),
             EvidenceFact(**{**fact('REP-002', 'site', 'S01', 'equipment_ok', True), 'status': 'unverified'}),
             EvidenceFact(**{**fact('REP-001', 'site', 'S01', 'equipment_ok', False), 'status': 'verified'})]
    accepted, rejected = normalize_facts(s, facts)
    assert len(rejected) == 2
    status = {f.evidence_ids[0]: f.status for f in accepted}
    assert status == {'REP-002': 'verified', 'REP-001': 'unverified'}  # source decides, not the model
    reports = {r.report_id: r for r in s.reports}
    assert all(f.observed_at_min == reports[f.evidence_ids[0]].observed_at_min for f in accepted)


def test_injection_proposal_never_changes_policy_and_is_measured():
    s = case('DEV-001')
    injection = next(d['report_id'] for d in TRUTH.load('DEV-001').distractor_reports if d['kind'] == 'prompt_injection')
    proposal = {'service_id': s.services[0].service_id, 'proposed_critical': True, 'evidence_ids': [injection],
                'reason': 'Message says hospital'}
    a = adapter([extraction(perfect_facts('DEV-001')), specialist(), specialist(proposals=[proposal]), review()])
    result = AgentOrchestrator(a).run(s, 'multi')
    assert result.metadata['priority_proposals'][0]['status'] == 'pending_human_decision'
    assert result.state.scenario.services == s.services
    metrics = truth_extraction_metrics(TRUTH.load('DEV-001'), result.metadata['raw_facts'], None, result.metadata)
    assert metrics['injection_followed'] is True and metrics['injection_flagged'] is False


def test_single_agent_one_context_analyse_then_self_review():
    s = case('DEV-003')
    a = adapter([analysis(perfect_facts('DEV-003'), ignored('DEV-003')), review()])
    result = AgentOrchestrator(a).run(s, 'single')
    assert result.status == 'awaiting_approval' and len(result.model_usage) == 2
    assert {m['sender'] for m in result.messages} <= {'single_agent', 'deterministic_scheduler', 'coordinator'}
    first, second = a.client.requests
    assert len(first['messages']) == 2
    roles = [m['role'] for m in second['messages']]
    assert roles == ['system', 'user', 'assistant', 'user']  # same agent remembers its own analysis
    assert json.loads(second['messages'][2]['content'])['finding'] == 'All jobs done'


def test_single_agent_self_challenge_reanalyses_in_same_context():
    s = case('DEV-001')
    wrong = [fact('REP-001', 'site', 'S02', 'equipment_ok', False)]
    challenge = {'report_id': 'REP-001', 'target_id': 'S02', 'attribute': 'equipment_ok', 'problem': 'wrong site'}
    a = adapter([analysis(wrong), review('revise', [challenge]), analysis(perfect_facts('DEV-001')), review()])
    result = AgentOrchestrator(a).run(s, 'single')
    assert result.status == 'awaiting_approval'
    assert {x.target_id for x in result.plan.actions} == {'S01'}
    assert len(a.client.requests[-1]['messages']) == 8


@pytest.mark.parametrize('variant', [{'reviewer_enabled': False}, {'feedback_enabled': False}])
def test_ablations(variant):
    s = case('DEV-001')
    wrong = [fact('REP-001', 'site', 'S02', 'equipment_ok', False)]
    challenge = {'report_id': 'REP-001', 'target_id': 'S02', 'attribute': 'equipment_ok', 'problem': 'wrong site'}
    a = adapter([extraction(wrong), specialist(), specialist(), review('revise', [challenge])])
    result = AgentOrchestrator(a, **variant).run(s, 'multi')
    if variant.get('reviewer_enabled') is False:
        assert result.status == 'awaiting_approval' and len(a.client.requests) == 3
    else:
        assert result.status == 'escalated' and 'feedback disabled' in result.reasons[0]


def test_escalation_on_api_failure_and_template_delegation():
    s = case('DEV-001')
    result = AgentOrchestrator(adapter([RuntimeError('offline')])).run(s, 'multi')
    assert result.status == 'escalated' and result.plan is None
    with pytest.raises(ValueError):
        approve_run(result, 'operator')
    template = AgentOrchestrator().run(s, 'template')
    assert template.mode == 'template'


def test_transient_error_is_retried_once(monkeypatch):
    monkeypatch.setattr('project.llm.client.RETRY_BACKOFF_SECONDS', 0)
    error = RuntimeError('rate limited')
    error.status_code = 429
    s = case('DEV-003')
    a = adapter([error, extraction(perfect_facts('DEV-003')), specialist(), specialist(), review()])
    result = AgentOrchestrator(a).run(s, 'multi')
    assert result.status == 'awaiting_approval'
    assert result.model_usage[0]['status'] == 'transient_error_retried' and result.model_usage[0]['http_status'] == 429


def test_budget_exhaustion_escalates():
    s = case('DEV-003')
    a = adapter([extraction(perfect_facts('DEV-003')), specialist()], RunBudget(max_calls=2))
    result = AgentOrchestrator(a).run(s, 'multi')
    assert result.status == 'escalated' and 'BudgetExceeded' in result.reasons[0]

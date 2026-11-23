"""Independent restoration simulator.

Inputs: the visible scenario, an approved plan, the matching approval, and a
separately supplied evaluator truth object. The simulator never reads the
planner's predicted restoration figures and never calls a model, network or
real equipment interface; it only evolves an in-memory copy of the world.

Time model (see docs/handoffs/zahra.md):
* all times are whole incident minutes; availability holds on half-open
  intervals [t0, t1); metrics integrate exactly over [0, horizon);
* events at the same minute are applied together before availability is
  re-evaluated, so a state at minute t reflects every event with time <= t.
  Consequences: an action whose work_end equals t is complete at t; a
  generator that expires at t supplies no power at t; a crew-loss observation
  at t leaves actions finishing at or before t completed;
* log order inside one minute: generator expiry, action completion, failures
  and pauses, observation, then the availability snapshot.
"""
from __future__ import annotations

import copy
from collections import defaultdict

from project.core.schemas import Approval, Plan, ScenarioInput, SimulationResult, VerifiedState
from project.core.state import digest
from project.data.evaluator import EvaluatorTruth

from .metrics import Segment, ServiceRef, compute_metrics, service_intervals

ENGINE_VERSION = '0.1'
_ORDER = {'generator_expired': 0, 'action_completed': 1, 'action_failed': 2,
          'action_paused': 2, 'action_skipped': 2, 'observation': 3, 'availability': 9}


class SimulationRejected(ValueError):
    """Approval, plan or truth is unusable; nothing was simulated."""

    def __init__(self, violations: list[str]):
        super().__init__('; '.join(violations))
        self.violations = violations


class TopologyError(ValueError):
    """Backhaul graph contains a cycle or a site that cannot reach the core."""


def evaluate_services(parents: dict, core_id: str, services: list, equipment: dict,
                      powered: set, links: dict) -> frozenset:
    """Return the set of available service IDs for one world state.

    ``parents`` maps site -> (parent, link_id). A service is available only if
    its site and every upstream site up to the core have working equipment and
    power, and every link on that path works. Each service is evaluated exactly
    once, so sites carrying several services or shared upstream paths never
    double count.
    """
    def site_up(site: str) -> bool:
        seen, cursor, ok = set(), site, True
        while cursor != core_id:
            if cursor in seen or cursor not in parents:
                raise TopologyError(f'Cyclic or disconnected backhaul at {cursor}')
            seen.add(cursor)
            parent, link_id = parents[cursor]
            ok = ok and bool(equipment[cursor]) and cursor in powered and bool(links[link_id])
            cursor = parent
        return ok

    return frozenset(s.service_id for s in services if site_up(s.site_id))


def _authorize(scenario: ScenarioInput, plan: Plan, approval: Approval, state: VerifiedState | None):
    problems = []
    if approval.decision != 'approve':
        problems.append('Approval decision is not approve')
    if plan.scenario_id != scenario.scenario_id:
        problems.append('Plan belongs to a different scenario')
    if (approval.plan_id, approval.state_version) != (plan.plan_id, plan.state_version):
        problems.append('Approval does not match plan ID or state version')
    if approval.plan_hash != digest(plan):
        problems.append('Plan content changed after approval')
    if approval.state_hash != plan.state_hash:
        problems.append('Approval state hash differs from the plan state hash')
    if state is not None:
        if state.scenario_id != scenario.scenario_id or state.state_version != approval.state_version:
            problems.append('Verified state version differs from approval')
        if digest(state) != approval.state_hash:
            problems.append('Verified state changed after approval')
        if digest(state.scenario) != digest(scenario):
            problems.append('Scenario differs from the approved verified state')
    if not scenario.policy.approved_for_simulation:
        problems.append('Service policy is not approved for simulation')
    if problems:
        raise SimulationRejected(problems)


def _check_plan(scenario: ScenarioInput, plan: Plan, road_by_edge: dict) -> list[str]:
    """Structural checks against the visible scenario only (no hidden truth)."""
    bad = []
    options = {o.action_id: o for o in scenario.action_options}
    crews = {c.crew_id: c for c in scenario.crews}
    gens = {g.generator_id: g for g in scenario.generators}
    ids = [a.action_id for a in plan.actions]
    if len(ids) != len(set(ids)):
        bad.append('Duplicate action IDs in plan')
    deployments = defaultdict(int)
    by_crew = defaultdict(list)
    for a in plan.actions:
        opt, crew = options.get(a.action_id), crews.get(a.crew_id)
        if opt is None or crew is None:
            bad.append(f'{a.action_id}: unknown action or crew')
            continue
        if (a.kind, a.target_id, a.generator_id) != (opt.kind, opt.target_id, opt.generator_id):
            bad.append(f'{a.action_id}: disagrees with action catalogue')
        if opt.required_skill not in crew.skills:
            bad.append(f'{a.action_id}: crew lacks skill')
        if a.work_end_min - a.work_start_min != opt.duration_minutes:
            bad.append(f'{a.action_id}: wrong work duration')
        if not max(scenario.current_time_min, crew.available_from_min) <= a.departure_min <= a.work_start_min \
                < a.work_end_min <= scenario.horizon_min:
            bad.append(f'{a.action_id}: timing outside current time/horizon/crew window')
        if opt.kind == 'generator_deploy':
            deployments[a.generator_id] += 1
            gen = gens.get(a.generator_id)
            if gen is None or gen.location not in a.travel_route:
                bad.append(f'{a.action_id}: generator unknown or not collected on route')
        by_crew[a.crew_id].append(a)
    for gid, n in deployments.items():
        if n > 1 or sum(deployments.values()) > scenario.policy.max_generator_deployments_per_scenario:
            bad.append('More than one generator deployment')
            break
    for cid, acts in by_crew.items():
        crew = crews.get(cid)
        if crew is None:
            continue
        location, ready = crew.location, max(scenario.current_time_min, crew.available_from_min)
        for a in sorted(acts, key=lambda x: (x.departure_min, x.work_start_min, x.action_id)):
            opt = options.get(a.action_id)
            if opt is None:
                continue
            if a.departure_min < ready:
                bad.append(f'{a.action_id}: overlaps previous crew work')
            if a.travel_route[0] != location or a.travel_route[-1] != opt.location:
                bad.append(f'{a.action_id}: route endpoints disagree with crew location or work site')
            travel = 0
            for p, q in zip(a.travel_route, a.travel_route[1:]):
                road = road_by_edge.get(frozenset((p, q)))
                if road is None:
                    bad.append(f'{a.action_id}: route uses unknown road {p}-{q}')
                else:
                    travel += road.travel_minutes
            if a.work_start_min < a.departure_min + travel:
                bad.append(f'{a.action_id}: work starts before arrival')
            ready, location = a.work_end_min, opt.location
    return bad


def _check_truth(scenario: ScenarioInput, truth: EvaluatorTruth) -> None:
    problems = []
    if truth.scenario_id != scenario.scenario_id:
        problems.append('Truth belongs to a different scenario')
    if set(truth.sites) != {s.site_id for s in scenario.sites}:
        problems.append('Truth sites do not match scenario')
    if set(truth.links) != {l.link_id for l in scenario.links}:
        problems.append('Truth links do not match scenario')
    if set(truth.roads) != {r.road_id for r in scenario.roads}:
        problems.append('Truth roads do not match scenario')
    if {c.crew_id for c in truth.crews} != {c.crew_id for c in scenario.crews}:
        problems.append('Truth crews do not match scenario')
    if {g.generator_id for g in truth.generators} != {g.generator_id for g in scenario.generators}:
        problems.append('Truth generators do not match scenario')
    for ev in truth.future_events:
        p = ev.truth_patch
        if p.crew_id not in {c.crew_id for c in scenario.crews} or p.available_until_min < ev.at_min:
            problems.append(f'{ev.event_id}: invalid crew patch')
    if problems:
        raise SimulationRejected(problems)


def _run(scenario, truth, plan_actions, events, *, road_by_edge, parents, services, horizon):
    """Execute actions against a private copy of truth; return log, segments, outcomes."""
    truth = copy.deepcopy(truth)
    equipment = {k: v.equipment_ok for k, v in truth.sites.items()}
    grid = {k: v.grid_power_ok for k, v in truth.sites.items()}
    links = dict(truth.links)
    roads_open = dict(truth.roads)
    t_crew = {c.crew_id: c for c in truth.crews}
    t_gen = {g.generator_id: g for g in truth.generators}
    options = {o.action_id: o for o in scenario.action_options}
    until = {cid: c.available_until_min for cid, c in t_crew.items()}
    patched = {}
    for ev in sorted(events, key=lambda e: (e.at_min, e.event_id)):
        p = ev.truth_patch
        patched[p.crew_id] = min(patched.get(p.crew_id, p.available_until_min), p.available_until_min)

    timeline = []   # (time, order, tiebreak, kind, payload)
    outcomes = {}
    by_crew = defaultdict(list)
    for a in plan_actions:
        by_crew[a.crew_id].append(a)
    for cid, acts in by_crew.items():
        blocked = None
        for a in sorted(acts, key=lambda x: (x.departure_min, x.work_start_min, x.action_id)):
            reason = None
            if blocked:
                outcomes[a.action_id] = ('skipped', f'earlier action {blocked} did not complete')
                timeline.append((a.departure_min, 'action_skipped', a.action_id,
                                 {'action_id': a.action_id, 'reason': outcomes[a.action_id][1]}))
                continue
            crew = t_crew[cid]
            if a.departure_min < crew.available_from_min or a.work_end_min > crew.available_until_min:
                reason = 'crew unavailable in actual crew window'
            for p, q in zip(a.travel_route, a.travel_route[1:]):
                road = road_by_edge[frozenset((p, q))]
                if not roads_open[road.road_id]:
                    reason = reason or f'road {road.road_id} is closed'
            if a.kind == 'generator_deploy':
                gen = t_gen[a.generator_id]
                if not gen.available:
                    reason = reason or 'generator unavailable'
                elif gen.location not in a.travel_route:
                    reason = reason or 'generator not collected at its actual location'
            if reason:
                outcomes[a.action_id] = ('failed', reason)
                timeline.append((a.departure_min, 'action_failed', a.action_id,
                                 {'action_id': a.action_id, 'reason': reason}))
                blocked = a.action_id
                continue
            if cid in patched and a.work_end_min > patched[cid]:
                at = min(e.at_min for e in events if e.truth_patch.crew_id == cid)
                outcomes[a.action_id] = ('paused', 'crew lost; unfinished work paused pending replan')
                timeline.append((at, 'action_paused', a.action_id,
                                 {'action_id': a.action_id, 'crew_id': cid, 'reason': outcomes[a.action_id][1]}))
                blocked = a.action_id
                continue
            outcomes[a.action_id] = ('completed', '')
            timeline.append((a.work_end_min, 'action_completed', a.action_id,
                             {'action_id': a.action_id, 'kind': a.kind, 'target_id': a.target_id,
                              'crew_id': cid, 'generator_id': a.generator_id}))
            if a.kind == 'generator_deploy':
                timeline.append((a.work_end_min + t_gen[a.generator_id].autonomy_minutes, 'generator_expired',
                                 a.generator_id, {'generator_id': a.generator_id, 'site_id': a.target_id}))
    for ev in events:
        timeline.append((ev.at_min, 'observation', ev.event_id,
                         {'event_id': ev.event_id, 'report_id': ev.operator_report.report_id,
                          'source_type': ev.operator_report.source_type,
                          'observed_at_min': ev.operator_report.observed_at_min,
                          'text': ev.operator_report.text, 'replan_required': True}))
    timeline.sort(key=lambda e: (e[0], _ORDER[e[1]], e[2]))

    gen_site: dict[str, str] = {}
    boundaries = sorted({0} | {t for t, *_ in timeline if 0 < t < horizon})
    log, segments = [], []
    idx = 0
    for i, b in enumerate(boundaries):
        while idx < len(timeline) and timeline[idx][0] <= b:
            t, kind, key, payload = timeline[idx]
            idx += 1
            if kind == 'action_completed':
                a = payload
                if a['kind'] == 'equipment_repair':
                    equipment[a['target_id']] = True
                elif a['kind'] == 'link_repair':
                    links[a['target_id']] = True
                else:
                    gen_site[a['generator_id']] = a['target_id']
            elif kind == 'generator_expired':
                gen_site.pop(key, None)
            log.append({'t': t, 'type': kind, **payload})
        powered = {s for s, g in grid.items() if g} | set(gen_site.values())
        avail = evaluate_services(parents, scenario.core_id, services, equipment, powered, links)
        end = boundaries[i + 1] if i + 1 < len(boundaries) else horizon
        segments.append(Segment(b, end, avail))
        log.append({'t': b, 'type': 'availability', 'available_services': sorted(avail),
                    'weighted_available': sum(s.weight for s in services if s.service_id in avail)})
    for t, kind, key, payload in timeline[idx:]:  # events at or after the horizon
        log.append({'t': t, 'type': kind, **payload})
    return log, segments, outcomes


def simulate(scenario: ScenarioInput, approved_plan: Plan, approval: Approval,
             isolated_truth: EvaluatorTruth, *, state: VerifiedState | None = None) -> SimulationResult:
    """Shared function agreement: simulate(scenario, approved_plan, approval, isolated_truth).

    ``state`` is optional; when given, the approval is additionally bound to the
    exact verified state. Inputs are never mutated.
    """
    _authorize(scenario, approved_plan, approval, state)
    _check_truth(scenario, isolated_truth)
    road_by_edge = {frozenset((r.origin, r.to)): r for r in scenario.roads}
    bad = _check_plan(scenario, approved_plan, road_by_edge)
    if bad:
        raise SimulationRejected(bad)
    parents = {l.child: (l.parent, l.link_id) for l in scenario.links}
    services = [ServiceRef(s.service_id, s.weight, s.critical) for s in scenario.services]
    kwargs = dict(road_by_edge=road_by_edge, parents=parents, services=scenario.services,
                  horizon=scenario.horizon_min)
    events = [e for e in isolated_truth.future_events if e.at_min < scenario.horizon_min]
    log, segments, outcomes = _run(scenario, isolated_truth, approved_plan.actions, events, **kwargs)
    _, base_segments, _ = _run(scenario, isolated_truth, [], [], **kwargs)

    metrics = compute_metrics(services, segments, scenario.horizon_min)
    base = compute_metrics(services, base_segments, scenario.horizon_min)
    metrics['baseline_weighted_downtime_min'] = base['weighted_downtime_min']
    metrics['weighted_downtime_reduction_min'] = base['weighted_downtime_min'] - metrics['weighted_downtime_min']
    metrics['actions_completed'] = sum(1 for s, _ in outcomes.values() if s == 'completed')
    metrics['actions_not_completed'] = sum(1 for s, _ in outcomes.values() if s != 'completed')

    final = segments[-1].available
    unmet = [f'service:{s.service_id}' for s in scenario.services if s.service_id not in final]
    completed = [e['action_id'] for e in log if e['type'] == 'action_completed']
    replan = any(e['type'] == 'observation' for e in log)
    metadata = {
        'engine_version': ENGINE_VERSION,
        'deterministic': True,
        'uses_model_or_network': False,
        'time_model': 'exact integer-minute event integration over half-open intervals [t0,t1); no sampling',
        'same_minute_rule': 'all events at minute t applied together before availability at t',
        'plan_id': approved_plan.plan_id,
        'approval_plan_hash': approval.plan_hash,
        'approval_state_version': approval.state_version,
        'planner_prediction_used': False,
        'service_availability': {
            s.service_id: {'weight': s.weight, 'critical': s.critical,
                           'intervals': service_intervals(segments, s.service_id),
                           'available_min': sum(e - b for b, e in service_intervals(segments, s.service_id))}
            for s in scenario.services},
        'action_outcomes': {k: {'status': v[0], 'reason': v[1]} for k, v in sorted(outcomes.items())},
        'replan_required': replan,
        'future_event_support': 'implemented; unit-tested; replanning loop not integrated (pending)',
    }
    return SimulationResult(scenario_id=scenario.scenario_id, plan_id=approved_plan.plan_id,
                            state_version=approved_plan.state_version, trajectory=log,
                            completed_actions=completed, unmet_needs=unmet, metrics=metrics,
                            run_metadata=metadata)


def session_callback(session, truth_loader):
    """Adapter for CoreSession(simulator=...).

    CoreSession verifies approval before calling; this adapter forwards the
    session's recorded approval so the simulator re-checks it independently.
    ``truth_loader`` is an EvaluatorLoader held by the harness, never by agents.
    """
    def callback(state: VerifiedState, plan: Plan) -> SimulationResult:
        truth = truth_loader.load(state.scenario_id)
        return simulate(state.scenario, plan, session.approval, truth, state=state)
    return callback

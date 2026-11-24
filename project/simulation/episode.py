"""Evaluator-side incident checkpoints. No future truth enters a visible snapshot.

Work finishing at an event time completes first. A lost crew's unfinished work
is cancelled without partial repair credit. Unaffected work already departed
continues under its original approval; later departures are cancelled. Replans
reserve these committed crews until work end, at their known destination.
"""
from __future__ import annotations

import copy
from collections import defaultdict

from project.core.schemas import ActiveGenerator, Report, ScenarioInput, SimulationResult
from project.core.state import digest
from .engine import SimulationRejected, _authorize, _check_plan, _check_truth, _run, evaluate_services
from .metrics import Segment, ServiceRef, compute_metrics, service_intervals


class IncidentEpisode:
    def __init__(self, scenario, truth):
        if scenario.current_time_min != 0:
            raise SimulationRejected(['An incident must start at minute zero'])
        _check_truth(scenario, truth)
        self._initial = scenario.model_copy(deep=True)
        self._truth = truth.model_copy(deep=True)
        self._expected = scenario.model_copy(deep=True)
        self._equipment = {k: v.equipment_ok for k, v in truth.sites.items()}
        self._grid = {k: v.grid_power_ok for k, v in truth.sites.items()}
        self._links = dict(truth.links)
        self._roads = dict(truth.roads)
        self._crews = {c.crew_id: c.model_copy(deep=True) for c in truth.crews}
        self._visible_crews = {c.crew_id: c.model_copy(deep=True) for c in scenario.crews}
        self._expected_expiry = {}
        self._generators = {g.generator_id: g.model_copy(deep=True) for g in truth.generators}
        self._parents = {l.child: (l.parent, l.link_id) for l in scenario.links}
        self._edges = {frozenset((r.origin, r.to)): r for r in scenario.roads}
        self._options = {a.action_id: a for a in scenario.action_options}
        self._active = {}  # generator -> (site, expiration)
        self._used_generators = set()
        self._queue = []
        self._pending = {}
        self._outcomes = {}
        self._completed = []
        self._log = []
        self._segments = []
        self._observations = []
        self._seen_events = set()
        self._used_plans = set()
        self._last_version = 0
        self._time = 0
        self._paused = False
        self._complete = False
        self._known = scenario.observed_state.model_copy(deep=True)

    @property
    def paused(self): return self._paused

    @property
    def complete(self): return self._complete

    def checkpoint(self):
        if not self._paused:
            raise SimulationRejected(['No paused checkpoint is available'])
        return self._expected.model_copy(deep=True)

    def _available(self):
        power = {s for s, v in self._grid.items() if v} | {s for s, end in self._active.values() if end > self._time}
        return evaluate_services(self._parents, self._initial.core_id, self._initial.services,
                                 self._equipment, power, self._links)

    def advance(self, scenario, plan, approval, *, state=None):
        """Transactionally advance one approved plan to the next incident event/end."""
        if self._complete:
            raise SimulationRejected(['Incident already completed'])
        if digest(scenario) != digest(self._expected):
            raise SimulationRejected(['Scenario differs from the live incident checkpoint'])
        _authorize(scenario, plan, approval, state)
        if self._last_version and (state is None or plan.state_version <= self._last_version):
            raise SimulationRejected(['Continuation requires a new verified state version and fresh approval'])
        if digest(plan) in self._used_plans:
            raise SimulationRejected(['Plan already executed'])
        if state is not None:
            from project.core.validator import validate
            if not validate(plan, state).valid:
                raise SimulationRejected(['Independent current-state validation failed'])
        bad = _check_plan(scenario, plan, self._edges)
        if bad:
            raise SimulationRejected(bad)
        # A failing callback must not leave half-advanced world state behind.
        candidate = copy.deepcopy(self)
        if state is not None:
            candidate._known = state.resolved_observations.model_copy(deep=True)
        candidate._advance(scenario, plan)
        candidate._last_version = plan.state_version
        candidate._used_plans.add(digest(plan))
        result = candidate._result(plan)
        self.__dict__.update(candidate.__dict__)
        return result

    def _advance(self, scenario, plan):
        self._paused = False
        # Reserve action IDs across episodes, including already committed work.
        for action in plan.actions:
            if action.action_id in self._completed or action.action_id in self._pending:
                raise SimulationRejected(['An action is already completed or committed'])
            if action.generator_id and action.generator_id in self._used_generators:
                raise SimulationRejected(['Generator cannot be redeployed'])
            self._pending[action.action_id] = action.model_copy(deep=True)
            self._queue.append((action.departure_min, 2, action.action_id, 'depart', action.action_id))
        hidden = [e for e in self._truth.future_events
                  if e.event_id not in self._seen_events and self._time < e.at_min <= scenario.horizon_min]
        stop = min([scenario.horizon_min, *[e.at_min for e in hidden]])
        while self._time < stop or any(e[0] == self._time for e in self._queue):
            next_time = min([stop, *[e[0] for e in self._queue if e[0] >= self._time]])
            if next_time > self._time:
                self._segments.append(Segment(self._time, next_time, self._available()))
                self._time = next_time
            due = sorted([e for e in self._queue if e[0] == self._time], key=lambda e: (e[1], e[2]))
            self._queue = [e for e in self._queue if e[0] != self._time]
            for _, _, key, kind, payload in due:
                if kind != 'depart': self._event(kind, key, payload)
            if self._time == stop:
                events = sorted([e for e in hidden if e.at_min == stop], key=lambda e: e.event_id)
                for event in events:
                    self._loss(event)
                if not events:
                    for _, _, key, kind, payload in due:
                        if kind == 'depart': self._event(kind, key, payload)
                if events and stop < scenario.horizon_min:
                    self._paused = True
                    self._snapshot(scenario)
                else:
                    self._complete = True
                self._log.append({'t': self._time, 'type': 'availability',
                                  'available_services': sorted(self._available())})
                break
            for _, _, key, kind, payload in due:
                if kind == 'depart': self._event(kind, key, payload)
            self._log.append({'t': self._time, 'type': 'availability',
                              'available_services': sorted(self._available())})
        if not self._complete and not self._paused and self._time == scenario.horizon_min:
            self._complete = True

    def _event(self, kind, key, payload):
        if kind == 'expire':
            self._active.pop(key, None)
            self._log.append({'t': self._time, 'type': 'generator_expired', 'generator_id': key})
            return
        action = self._pending.get(key)
        if action is None: return
        crew = self._crews[action.crew_id]
        if kind == 'depart':
            reason = None
            if crew.location != action.travel_route[0]:
                reason = 'Actual crew position differs from route origin'
            if self._options[key].required_skill not in crew.skills:
                reason = 'Actual crew lacks required skill'
            if action.work_end_min > crew.available_until_min or action.departure_min < crew.available_from_min:
                reason = 'Crew unavailable in actual window'
            for p, q in zip(action.travel_route, action.travel_route[1:]):
                if not self._roads[self._edges[frozenset((p, q))].road_id]:
                    reason = 'Access road closed'
            if action.generator_id:
                gen = self._generators[action.generator_id]
                if not gen.available or gen.location not in action.travel_route:
                    reason = 'Generator unavailable at pickup location'
            if reason:
                self._outcomes[key] = {'status': 'failed', 'reason': reason}
                self._pending.pop(key)
                self._log.append({'t': self._time, 'type': 'action_failed', 'action_id': key, 'reason': reason})
                # Later tasks depend on the failed journey's destination.
                for other in list(self._pending.values()):
                    if other.crew_id == action.crew_id and other.departure_min >= self._time:
                        self._pending.pop(other.action_id)
                        self._outcomes[other.action_id] = {'status': 'skipped', 'reason': 'Earlier crew action failed'}
                return
            self._outcomes[key] = {'status': 'in_progress', 'reason': ''}
            if action.generator_id:
                self._used_generators.add(action.generator_id)
                self._generators[action.generator_id].available = False
            self._queue.append((action.work_end_min, 1, key, 'complete', None))
            self._log.append({'t': self._time, 'type': 'action_started', 'action_id': key})
        elif kind == 'complete':
            self._pending.pop(key)
            crew.location = self._options[key].location
            self._visible_crews[action.crew_id].location = crew.location
            if action.kind == 'equipment_repair':
                self._equipment[action.target_id] = True
                self._known.sites[action.target_id].equipment_ok = True
                phrase = 'equipment is operational'
            elif action.kind == 'link_repair':
                self._links[action.target_id] = True
                self._known.links[action.target_id] = True
                phrase = 'backhaul link is operational'
            else:
                generator = self._generators[action.generator_id]
                generator.location = action.target_id
                expiry = self._time + generator.autonomy_minutes
                self._active[action.generator_id] = (action.target_id, expiry)
                public = next(g for g in self._initial.generators if g.generator_id == action.generator_id)
                self._expected_expiry[action.generator_id] = self._time + public.autonomy_minutes
                self._queue.append((expiry, 0, action.generator_id, 'expire', None))
                phrase = None
            if phrase:
                self._observations.append(Report(report_id='SIM-' + key, source_type='simulated_completion',
                    observed_at_min=self._time, received_at_min=self._time, text=f'{action.target_id}: {phrase}.'))
            self._outcomes[key] = {'status': 'completed', 'reason': ''}
            self._completed.append(key)
            self._log.append({'t': self._time, 'type': 'action_completed', 'action_id': key,
                              'kind': action.kind, 'target_id': action.target_id})

    def _loss(self, event):
        self._seen_events.add(event.event_id)
        crew = self._crews[event.truth_patch.crew_id]
        crew.available_until_min = min(crew.available_until_min, event.truth_patch.available_until_min)
        self._visible_crews[crew.crew_id].available_until_min = crew.available_until_min
        report = event.operator_report
        self._observations.append(Report(report_id=report.report_id, source_type=report.source_type,
            observed_at_min=report.observed_at_min, received_at_min=self._time, text=report.text))
        self._log.append({'t': self._time, 'type': 'observation', 'report_id': report.report_id,
                          'text': report.text, 'replan_required': True})
        for action in list(self._pending.values()):
            started = self._outcomes.get(action.action_id, {}).get('status') == 'in_progress'
            if started and action.crew_id != crew.crew_id:
                continue  # Original approval permits completion of already-started unaffected work.
            self._pending.pop(action.action_id)
            self._queue = [e for e in self._queue if e[2] != action.action_id]
            self._outcomes[action.action_id] = {'status': 'paused' if started else 'cancelled',
                'reason': 'Resource change requires fresh review; unfinished work receives no repair credit'}
            if started:
                # Last reached node is retained for a lost crew in transit; the crew
                # is unavailable, so this location never authorizes a new journey.
                reached = action.travel_route[0]
                elapsed = action.departure_min
                for left, right in zip(action.travel_route, action.travel_route[1:]):
                    elapsed += self._edges[frozenset((left, right))].travel_minutes
                    if elapsed <= self._time: reached = right
                crew.location = reached
                self._visible_crews[crew.crew_id].location = reached
            self._log.append({'t': self._time, 'type': 'action_paused' if started else 'action_cancelled',
                              'action_id': action.action_id})

    def _snapshot(self, scenario):
        payload = scenario.model_dump(mode='json', by_alias=True)
        payload['current_time_min'] = self._time
        payload['observed_state'] = self._known.model_dump(mode='json')
        payload['reports'] = [*payload['reports'], *[r.model_dump(mode='json') for r in self._observations
                             if r.report_id not in {r['report_id'] for r in payload['reports']}]]
        crews = {c['crew_id']: c for c in payload['crews']}
        for cid, actual in self._visible_crews.items():
            crews[cid]['available_until_min'] = actual.available_until_min
            crews[cid]['available_from_min'] = min(crews[cid]['available_from_min'], max(0, actual.available_until_min - 1))
            crews[cid]['location'] = actual.location
        for action in self._pending.values():
            crews[action.crew_id]['location'] = self._options[action.action_id].location
            crews[action.crew_id]['available_from_min'] = action.work_end_min
        payload['crews'] = list(crews.values())
        for gen in payload['generators']:
            actual = self._generators[gen['generator_id']]
            if gen['generator_id'] in self._used_generators:
                gen['available'] = False
                gen['location'] = actual.location
        payload['active_generators'] = [ActiveGenerator(generator_id=gid, site_id=site, expires_at_min=self._expected_expiry[gid]).model_dump()
            for gid, (site, end) in self._active.items() if end > self._time and self._expected_expiry[gid] > self._time]
        payload['action_options'] = [a for a in payload['action_options']
            if a['action_id'] not in self._completed and a['action_id'] not in self._pending]
        self._expected = ScenarioInput.model_validate(payload)

    def _result(self, plan):
        services = [ServiceRef(s.service_id, s.weight, s.critical) for s in self._initial.services]
        metrics = compute_metrics(services, self._segments, self._time)
        metrics['measured_duration_min'] = self._time
        metrics['horizon_min'] = self._initial.horizon_min
        metrics['observed_until_min'] = self._time
        metrics['incident_horizon_min'] = self._initial.horizon_min
        final = self._available()
        metrics['unmet_needs_count'] = len(services) - len(final)
        if self._complete:
            if metrics['first_restoration_min'] is None and final - self._segments[-1].available:
                metrics['first_restoration_min'] = self._time
            metrics['services_available_at_horizon_end'] = len(final)
            _, baseline_segments, _ = _run(self._initial, self._truth, [], [], road_by_edge=self._edges,
                parents=self._parents, services=self._initial.services, horizon=self._initial.horizon_min)
            baseline = compute_metrics(services, baseline_segments, self._initial.horizon_min)
            metrics['baseline_weighted_downtime_min'] = baseline['weighted_downtime_min']
            metrics['weighted_downtime_reduction_min'] = baseline['weighted_downtime_min'] - metrics['weighted_downtime_min']
        else:
            for name in ('weighted_available_min', 'weighted_downtime_min', 'unweighted_available_min',
                         'unweighted_downtime_min', 'critical_service_downtime_min', 'unweighted_availability'):
                metrics[name.replace('_min', '_so_far_min') if name.endswith('_min') else name + '_so_far'] = metrics[name]
                metrics[name] = None
            metrics['total_weighted_horizon_min'] = sum(s.weight for s in services) * self._initial.horizon_min
            metrics['services_available_at_horizon_end'] = None
        metrics['actions_completed'] = len(self._completed)
        return SimulationResult(scenario_id=self._initial.scenario_id, plan_id=plan.plan_id,
            state_version=plan.state_version, trajectory=copy.deepcopy(self._log),
            completed_actions=[a for a in self._completed if a in {x.action_id for x in plan.actions}],
            unmet_needs=[f'service:{s.service_id}' for s in services if s.service_id not in final], metrics=metrics,
            run_metadata={'engine_version': '0.2', 'measurement_scope': 'complete_incident' if self._complete else 'elapsed_prefix',
                'replan_required': self._paused, 'observed_until_min': self._time,
                'planner_prediction_used': False, 'uses_model_or_network': False,
                'action_outcomes': copy.deepcopy(self._outcomes), 'all_completed_actions': list(self._completed),
                'committed_actions': [a.model_dump(mode='json') for a in self._pending.values()
                                      if self._outcomes.get(a.action_id, {}).get('status') == 'in_progress'],
                'service_availability': {s.service_id: {'weight': s.weight, 'critical': s.critical,
                    'intervals': service_intervals(self._segments, s.service_id)} for s in services},
                'same_minute_rule': 'expiry, completed work, departures, resource observations; intervals are half-open',
                'continuation_policy': 'lost work restarts without partial credit; unaffected departed work completes under prior approval'})

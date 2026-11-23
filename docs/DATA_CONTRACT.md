# RE:L!NK core contracts version 0.1

The executable models in `project/core/schemas.py` are the implementation authority. They accept the starter pack's processed agent input JSON directly. Do not pass raw combined scenario/truth objects to these models.

## Input compatibility

`ScenarioInput` uses the exact fixture keys: `schema_version`, `scenario_id`, `region_label`, `current_time_min`, `horizon_min`, `core_id`, `depot_id`, `sites`, `links`, `roads`, `services`, `crews`, `generators`, `observed_state`, `action_options`, `reports` and `policy`. Roads serialize with the original `from` key; Python code accesses `road.origin`.

Nested models reject extra keys, invalid identifiers/references, duplicate undirected road edges, disconnected/cyclic backhaul, mismatched policy weights, invalid crew windows, action-catalogue inconsistencies and future evidence. Observation health values accept actual booleans or null, not string/number substitutes. Unknowns remain null.

Version 0.1 supports a directed tree rooted at CORE, with one parent per site, distinct undirected road edges, static resources and one generator deployment across the incident. Arbitrary mesh topology, overlapping site coverage/population estimates, active partial jobs and generator redeployment are not represented.

## Shared functions

```python
from project.core.state import build_verified_state
from project.core.planner import plan, greedy_plan
from project.core.validator import validate
from project.core.coordinator import approve, check_approval, Coordinator

state = build_verified_state(scenario, facts, confirmations=None, state_version=1)
candidate = plan(state, solver_seconds=5, seed=22)
validation = validate(candidate, state)
approval = approve(candidate.plan_id, state.state_version, "approve",
                   plan=candidate, state=state, operator_id="operator-name")
check_approval(approval, candidate, state)
```

Zahra implements `load_case(path) -> ScenarioInput` using an allowlisted processed input root. A deliberate human CLI path is not an agent filesystem tool.

Zahra also implements `simulate(scenario, approved_plan, approval, isolated_truth) -> SimulationResult`. Her evaluator supplies hidden truth independently; no core runtime module imports an evaluator loader. The simulator must check approval/current state at its boundary, preserve history across future events and never give hidden future information to the agents.

## Objects

- `EvidenceFact`: target_type, target_id, attribute, value, evidence_ids, status and reason. Supported attributes are site equipment/power, link backhaul and road access. A citation must be an existing report ID.
- `VerifiedState`: scenario ID/version, source hash, typed visible scenario, resolved observations, facts and unresolved keys. It contains no evaluator truth. Always rebuild a new version after a material operator update.
- `ScheduledAction`: catalogue action ID/type/target, assigned crew, optional generator, departure minute, explicit node route, work start and work end. Work duration excludes travel.
- `Plan`: plan ID, scenario ID/version, state content hash, scheduled actions, unmet needs, citations, planner configuration and explanation.
- `ValidationResult`: valid plus structured violations carrying code, action ID and reason.
- `Approval`: plan ID/version, plan hash, state hash, operator decision/identity and timestamp. These content hashes are additional fields beyond the earlier planning guides; both plan and state must still match at execution. Hash binding prevents accidental/stale approval, not malicious replacement of approval records; authentication/storage remains a UI integration task.
- `SimulationResult`: scenario ID, plan ID/version, trajectory, completed action IDs, unmet needs, numeric metrics and run metadata. The model is supplied; the simulation implementation belongs to Zahra.

## Evidence and uncertainty

The resolver checks report existence, asset references, source authority and conflicting values. `authoritative_snapshot`, `confirmed_field_update` and recorded `operator_confirmation` are recognized authoritative source types. Unverified/stale fixture messages cannot override authoritative evidence. Equally authoritative contradictions remain unknown; model confidence cannot settle them. Operator confirmations must cite a recorded operator-confirmation report in the visible scenario.

Source consistency does not prove a model's semantic reading is correct. Hosted facts remain susceptible to misinterpretation; independent review and human confirmation are still needed. Tests use a narrowly labelled exact-template parser, not claimed general language understanding.

The coordinator currently escalates if **any** unresolved asset fact remains. This is conservative: it does not yet distinguish action-critical unknowns from unrelated unknowns. Missing resources can still produce a valid partial/empty schedule with explicit unmet needs.

## Time and metrics

The CP-SAT model requires current time, horizon, work durations and generator autonomy on five-minute boundaries; unsupported inputs fail explicitly. Road travel is rounded upward for solver timing and independently rechecked in actual minutes. Generator power lasts from deployment completion until completion plus autonomy. Crew routes visit the generator's actual initial location before deployment. A virtual solver return arc is not a physical return-to-depot trip.

The primary model objective maximizes predicted weighted service availability over the remaining horizon. It accounts for equipment, power, each upstream site's status and each backhaul link. Fewer actions, then earlier completions are secondary tie-breakers. Config includes solver status/bound, seed, worker count, slot length and **predicted** remaining availability/downtime. OPTIMAL refers only to this encoded static model; it is not evidence of real-world or hidden-world optimality.

The independent simulator must compute actual evaluation downtime over the complete 720-minute horizon. For replanning, retain prior interval contributions; do not reset the clock. Never display planner predictions as measured simulator results.


## Dashboard planning boundary (Push 3)

Dashboard consumers use CoreSession with a fresh Coordinator per explicit generation request. Prepare reserves monotonically increasing state versions even after a failed attempt or UI-cleared plan, and the next version advances beyond any evidence-review revisions. Scenario changes create a fresh session with content-bound approval still required. UI request deduplication is an additional per-browser-session guard, not a durable transaction mechanism. Read `docs/DASHBOARD_PUSH3.md` for request/failure behavior; operator approval and simulator execution remain the next integration milestone.


## Operator review and simulator boundary (Push 4)

Dashboard approval/rejection uses the current reviewed RunResult, an exact previously displayed binding and a fresh allowlisted source-file hash. Decisions become active only after their private audit record is written. Rejected runs require a new plan; historical records never automatically restore authorization. The `simulate_approved` service additionally requires matching operator/approval, an explicitly attached backend callback and no prior attempt for that plan hash. It validates returned SimulationResult identity, completed action IDs and finite metrics before exposure. This is interface validation, not independent metric verification. See `docs/DASHBOARD_PUSH4.md` for the synchronous callback adapter contract and hidden-truth isolation. No independent simulator implementation is bundled with this UI checkpoint.


## Result presentation and history (Push 5)

History is an allowlisted, bounded, read-only view of saved records; it never restores plans or authorization. SimulationResult metrics preserve nulls and use explicit run_metadata.metric_units when available. The trajectory table preserves reported flat fields; optional run_metadata.trajectory_plot supplies documented time_field/series/time_unit defaults. Without those defaults the operator explicitly selects numeric plotting fields; meanings/units are not inferred. Non-finite output is rejected before JSON serialization. See docs/DASHBOARD_PUSH5.md for record cross-linking, scope and limits. This completes the dashboard presentation interface, not real simulator validation.

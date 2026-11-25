# RE:L!NK — Day 1 execution plan

**Date:** Sunday 22 November 2026. **Working hours:** 09:00–18:30, Sri Lanka time. **Internal release target:** 28 November, 18:00.

Tomorrow combines our build Phase 1 (foundations and data) and the first slice of build Phase 2 (planning and simulation). These are internal build phases, not a change to the competition's official phase names. The proposal's earlier planned start was 20 November; report actual implementation dates honestly.

## One measurable Day 1 goal
An operator loads the five-site demo, reviews cited fault evidence, obtains a feasible crew/generator plan, approves it, and sees simulated connectivity change over time. The UI clearly identifies synthetic data. A rejected plan displays concrete violations. Do not try to complete four agents, a production backend or real telecom integration tomorrow.

## Ownership and difficulty
| Owner | Assignment | Concrete handover | Acceptance check |
|---|---|---|---|
| Ihthisham Irshad — hardest | Contracts, deterministic planning/validation, coordinator, hosted-model adapter and integration | `project/core/schemas.py`, `planner.py`, `validator.py`, `coordinator.py`, `project/llm/client.py`; first single-agent call path | No crew overlap; skills, routes, time horizon and generator uniqueness respected; model output must validate before use |
| Zahra Hassan — substantial data work | Run data pipeline, inspect development fixtures, implement independent graph simulator and metrics | `project/data/loader.py`, `project/simulation/engine.py`, `metrics.py`; data quality notes | S02+S04 recover when S02 is generator-powered in the demo; S01 branch stays down; service falls again when fuel runs out |
| Eyaas Ajmal — UI/integration | Streamlit dashboard and operator controls | `project/ui/app.py`; scenario, evidence, plan, approval and trajectory views | Run button makes one explicit run; UI rerenders do not call the API; approve/reject tied to current plan version |
| Kiruthika Vijayakumar — easiest, bounded | Manual CSV review, demo walkthrough, source register, screenshots and draft documentation | `docs/manual_qa.csv`; notes for existing Workflow and PROJECT_DETAILS files | Open demo + 10 development cases; identify IDs, nulls, contradictions and resources; record PASS/FAIL only after checking |

Ihthisham owns the hardest engineering decisions, but should not become the only person who can integrate changes. Zahra and Eyaas agree their interfaces with him at 09:00. Kiruthika's scope is concrete manual work; she does not need to implement the optimizer, simulator or LLM integration.

## Shared schedule
| Sri Lanka time | Everyone / integration gate | Individual work |
|---|---|---|
| 09:00–09:25 | Agree five-site input/output and definition of restored service | Run starter data checks; create feature branches |
| 09:25–10:30 | Phase 1: contracts and data | Ihthisham defines schemas; Zahra validates data and loader; Eyaas builds UI shell; Kiruthika inspects demo tables |
| 10:30–12:30 | Phase 2: first implementation | Ihthisham builds feasible planner/validator; Zahra implements graph state and generator expiry; Eyaas renders evidence/plan; Kiruthika records QA |
| 12:30–13:15 | Break and first integration | One fixed sample plan travels through planner → simulator → UI, even before an LLM is connected |
| 13:15–15:00 | Build the end-to-end slice | Add independent validation and approval; one model-assisted evidence extraction path; keep an explicit deterministic test mode |
| 15:00–16:30 | Edge cases | Closed road, unavailable skill, null fact, conflict and generator depletion; show unmet needs and ask for human confirmation |
| 16:30–17:30 | Integrate and inspect | Each owner demonstrates their acceptance check; fix interface mismatches |
| 17:30–18:30 | Day-end gate | Fresh environment run, 2-minute walkthrough, reviewed commits, issue list and accurate documentation |

## Minimum implementation sequence
1. Parse the five-site JSON into typed objects. Reject bad references and impossible units.
2. Build distinct backhaul and road graphs. Roads are undirected for these fictional fixtures; backhaul has a directed core dependency. Depot is not a telecom node.
3. Extract report facts with their report IDs. Preserve unknowns. Contradictory authoritative reports require confirmation; do not let a model invent a resolution.
4. Produce a feasible plan on five-minute slots. Include travel, qualifications, crew availability, one generator deployment and a 12-hour horizon. A small greedy baseline can unblock integration before CP-SAT is complete; label it accurately.
5. Independently validate the proposed schedule against verified observations. The validator never reads evaluator truth.
6. Display plan and violations. Approval is explicit and linked to plan/state versions. Changing inputs invalidates approval.
7. Simulate approved actions using isolated truth, recording service availability at each event. Do not let agent tools import that truth.
8. Compute weighted service-minutes and unweighted service-minutes, plus time-to-first-restoration, unscheduled needs and constraint violations. Do not claim customer counts from these fictional services.
9. Save one reproducible run: scenario/version/hash, planner/model configuration, evidence references, approvals, schedule, trajectories, tokens, latency, errors and failures.
10. Add one genuine hosted-model extraction run if quota permits. A mock/replay demonstration must be labelled and must not be scored as a fresh model run.

## Five-site walkthrough
At the start, S01 and S02 have no grid power and L01 has failed. Their downstream services also fail. Sending a generator to S02 can restore **S02 and S04** while it has fuel; S01, S03 and S05 remain disconnected. Fixing L01 alone cannot restore the S01 branch while S01 is still unpowered. With one generator and no refuelling, not every service can stay restored. The honest output includes these unmet needs.

The fixture's S02 service has a synthetic weight of 5, and S04 has weight 1. Their joint available weight is 6; this is an illustrative policy, not six real customers or measured commercial value. Count generator autonomy from deployment completion, stop availability at depletion, and evaluate the whole 720-minute window.

## Working rules
- Branch suggestions: `feature/core-planner`, `feature/data-simulator`, `feature/dashboard`, `docs/qa`. Integrate reviewed small changes twice tomorrow. Check the existing repository structure before adding files.
- Keep API configuration in local environment variables; commit only placeholder examples. No key is needed for the included scripts.
- Use an OpenAI/OpenRouter adapter if both are being tested; record gateway, model ID and settings. Do not auto-route across random models in a formal comparison.
- Reserve roughly 8–12 real API requests for Day 1. Data generation, simulator tests and UI development should make zero model calls.
- Free hosted access is quota-limited and availability varies. If quota blocks the model call, finish the deterministic slice, label it, and log the blocked integration task.
- At day end, update actual progress and model/tool disclosures in the existing project documents; do not overwrite the submitted proposal.

## Definition of done
- [ ] Included data checks pass; manual review has named reviewer, date and actual findings.
- [ ] Five-site case loads in dashboard with a visible synthetic label.
- [ ] Planner emits a feasible schedule or an explicit infeasibility/unmet-needs explanation.
- [ ] Validator catches double booking, wrong skills, closed routes and generator reuse.
- [ ] Plan approval is required before simulation; changing state invalidates prior approval.
- [ ] Simulator passes the S02/S04 dependency example and generator-expiry example.
- [ ] One single-agent extraction route is implemented; real-call status and failures are recorded honestly.
- [ ] Run data and source versions are recorded; no keys committed.

## Remaining week
| Date | Finish by evening |
|---|---|
| 23 November | Expand to 15–20 sites; finish CP-SAT and deterministic baseline; robust data contracts |
| 24 November | Four agent roles with explicit shared state, evidence links and stop/escalation rules |
| 25 November | Replanning, reviewer and human approval; independent scenario audit and evaluation freeze |
| 26 November | Fair single-agent/multi-agent evaluation and ablations; start early enough for API quotas |
| 27 November | Fix failures; rerun only affected checks; finalize UI, documented results and video script |
| 28 November | Reproduce, finish walkthrough video and submission files; freeze by 18:00 |

The evaluation workload needs a quota check tomorrow: 20 cases × 3 repeats × 4 configurations = 240 runs if both ablations are separate. At the proposed maximum of 12 calls per run that is up to 2,880 calls. A small free allowance cannot be assumed to cover it. Decide the budget/provider/run schedule early and document any reduction in evaluation scope rather than inventing missing results.

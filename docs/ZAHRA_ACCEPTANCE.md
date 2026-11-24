# Zahra scope acceptance matrix

Against RELINK_Zahra_Work_Guide.docx and
RELINK_Zahra_Data_and_Simulation_Handbook.docx, prepared 22 November 2026.
Engineering acceptance and external research validation are separate statuses.

| Requirement | Delivered evidence | Status |
|---|---|---|
| Starter inventory, public provenance and synthetic/real separation | data/ATTRIBUTION.md, source manifest, 25/3 districts, 1/10/20 scenarios | Implemented and checked |
| Preserve nulls, stale/conflicting reports and units | preparation scripts, automated audit, tests/data | Implemented and checked |
| Typed allowlisted loader; references, cycles, evidence time, path errors | loader + shared schemas + loader/release tests | Implemented and checked |
| Truth isolation and matching scenario identity | separate evaluator loader; runtime-import isolation tests | Implemented and checked |
| Independent physical simulator and numerical demo | engine, metrics, hand calculations and tests/simulation | Implemented and checked |
| Approval, version, plan/content binding and input immutability | engine/episode authorization and integration tests | Implemented and checked |
| Crew loss, completed-work retention and fresh-approved continuation | IncidentEpisode, safe checkpoint, two-approval browser/service tests | Implemented and checked |
| Accumulated 720-minute metrics, generator expiry, half-open boundaries | prefix/null full-horizon metrics; final integration and numerical tests | Implemented and checked |
| Dashboard consumes actual SimulationResult | connected static/dynamic browser rehearsals and recorded results | Implemented and checked |
| Freeze data and prevent silent regeneration | 201-file frozen snapshot + guards and tamper/overwrite tests | Implemented and checked |
| Reproducible handoff, dependencies and actual AI/tool disclosures | handoffs/zahra.md, PROJECT_DETAILS.md, pinned requirements | Delivered |
| Independent human review and diversified held-out validation | automated audit + explicit PENDING human review sheet | External review still required |

## Actual checks

Final full pytest result: **351 passed**, zero failures/skips, in 33.80 seconds
on the team macOS/Python 3.11 environment. The preprocessing reproduction test
rebuilds a copied release byte-for-byte without modifying the original data.
Offline delivery smoke: 31 cases, 25 completed, six expected escalations,
zero model calls. Numeric outcomes are mechanism/plumbing acceptance, not evidence
of hosted multi-agent superiority or savings. The human-review row is not counted
as completed; do not describe the entire research/evaluation assignment as 100%
validated while it remains pending.

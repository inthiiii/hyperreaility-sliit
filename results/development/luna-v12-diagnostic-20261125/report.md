# Luna development verification

Development observations only. Independent held-out review and final evaluation remain pending.

Model: `gpt-6-luna`; reasoning: `none`.
Cases: 10; attempts: 120; concurrent batches: 10.

| Variant | Scored | Escalated | Failed | Incomplete | Model calls |
|---|---:|---:|---:|---:|---:|
| single | 12 | 18 | 0 | 0 | 115 |
| multi | 12 | 18 | 0 | 0 | 113 |
| no_reviewer | 16 | 14 | 0 | 0 | 80 |
| no_feedback | 13 | 17 | 0 | 0 | 105 |

Comparable scored single/multi pairs: 9 of 30.
Multi wins: 0; single wins: 0; ties: 9.
Mean single-minus-multi weighted downtime: 0 weighted service-minutes (complete comparable pairs only).

Raw initial extraction micro-F1: 1.0; metric-bearing run records: 120.
Labels cover recognized fixture sentences, not an independently audited natural-language dataset.

Escalations include unresolved evidence, agent review/clarification and workflow exceptions or budget stops; they are not all verified-correct safety decisions.
Failures and exclusions remain in the JSON report. Repetitions are not independent new scenarios. Applied action holds are not proof of better restoration. Actual API charges were not measured. No multi-agent superiority claim is made.

Wall times include concurrent batch contention and must not be presented as an isolated latency benchmark.

Source fingerprint: `3cf1bb392a3dae56c08c0a574ab78d3bdf4a2674c8b06248ad3aedb106c26bb3`.

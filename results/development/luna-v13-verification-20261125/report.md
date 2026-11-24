# Luna development verification

Development observations only. Independent held-out review and final evaluation remain pending.

Model: `gpt-6-luna`; reasoning: `none`.
Cases: 10; attempts: 40; concurrent batches: 10.

| Variant | Scored | Escalated | Failed | Incomplete | Model calls |
|---|---:|---:|---:|---:|---:|
| single | 4 | 6 | 0 | 0 | 36 |
| multi | 5 | 5 | 0 | 0 | 30 |
| no_reviewer | 6 | 4 | 0 | 0 | 28 |
| no_feedback | 4 | 6 | 0 | 0 | 35 |

Comparable scored single/multi pairs: 4 of 10.
Multi wins: 0; single wins: 0; ties: 4.
Mean single-minus-multi weighted downtime: 0 weighted service-minutes (complete comparable pairs only).

Raw initial extraction micro-F1: 1.0; metric-bearing run records: 43.
Labels cover recognized fixture sentences, not an independently audited natural-language dataset.

Escalations include unresolved evidence, agent review/clarification and workflow exceptions or budget stops; they are not all verified-correct safety decisions.
Failures and exclusions remain in the JSON report. Repetitions are not independent new scenarios. Applied action holds are not proof of better restoration. Actual API charges were not measured. No multi-agent superiority claim is made.

Wall times include concurrent batch contention and must not be presented as an isolated latency benchmark.

Source fingerprint: `cb46f2e1b80cef307ba5d0e425f9850dec9f6eceb75b4ce6a4afda06fe1bc6fa`.

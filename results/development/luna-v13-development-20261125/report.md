# Luna development verification

Development observations only. Independent held-out review and final evaluation remain pending.

Model: `gpt-6-luna`; reasoning: `none`.
Cases: 10; attempts: 120; concurrent batches: 10.

| Variant | Scored | Escalated | Failed | Incomplete | Model calls |
|---|---:|---:|---:|---:|---:|
| single | 16 | 14 | 0 | 0 | 110 |
| multi | 12 | 18 | 0 | 0 | 102 |
| no_reviewer | 17 | 13 | 0 | 0 | 84 |
| no_feedback | 12 | 18 | 0 | 0 | 100 |

Comparable scored single/multi pairs: 12 of 30.
Multi wins: 0; single wins: 0; ties: 12.
Mean single-minus-multi weighted downtime: 0 weighted service-minutes (complete comparable pairs only).

Raw initial extraction micro-F1: 1.0; metric-bearing run records: 129.
Labels cover recognized fixture sentences, not an independently audited natural-language dataset.

Escalations include unresolved evidence, agent review/clarification and workflow exceptions or budget stops; they are not all verified-correct safety decisions.
Failures and exclusions remain in the JSON report. Repetitions are not independent new scenarios. Applied action holds are not proof of better restoration. Actual API charges were not measured. No multi-agent superiority claim is made.

Wall times include concurrent batch contention and must not be presented as an isolated latency benchmark.

Source fingerprint: `cb46f2e1b80cef307ba5d0e425f9850dec9f6eceb75b4ce6a4afda06fe1bc6fa`.

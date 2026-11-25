# Luna development verification

Development observations only. Independent held-out review and final evaluation remain pending.

Model: `gpt-6-luna`; reasoning: `none`.
Cases: 10; attempts: 120; concurrent batches: 5.

| Variant | Scored | Escalated | Failed | Incomplete | Model calls |
|---|---:|---:|---:|---:|---:|
| single | 13 | 17 | 0 | 0 | 94 |
| multi | 12 | 18 | 0 | 0 | 89 |
| no_reviewer | 17 | 13 | 0 | 0 | 79 |
| no_feedback | 11 | 19 | 0 | 0 | 95 |

Comparable scored single/multi pairs: 8 of 30.
Multi wins: 0; single wins: 0; ties: 8.
Mean single-minus-multi weighted downtime: 0 weighted service-minutes (complete comparable pairs only).

Raw initial extraction micro-F1: 0.8977777777777778; metric-bearing run records: 130.
Labels cover recognized fixture sentences, not an independently audited natural-language dataset.

Escalations include unresolved evidence, agent review/clarification and workflow exceptions or budget stops; they are not all verified-correct safety decisions.
Failures and exclusions remain in the JSON report. Repetitions are not independent new scenarios. Applied action holds are not proof of better restoration. Actual API charges were not measured. No multi-agent superiority claim is made.

Wall times include concurrent batch contention and must not be presented as an isolated latency benchmark.

Source fingerprint: `dafc6722b279e749b0648a3235a165787d4763523b6d00f56a8f97c5091e3d87`.

# Luna development verification

Development observations only. Independent held-out review and final evaluation remain pending.

Model: `gpt-6-luna`; reasoning: `none`.
Cases: 10; attempts: 120; concurrent batches: 5.

| Variant | Scored | Escalated | Failed | Incomplete | Model calls |
|---|---:|---:|---:|---:|---:|
| single | 10 | 20 | 0 | 0 | 81 |
| multi | 8 | 22 | 0 | 0 | 78 |
| no_reviewer | 16 | 14 | 0 | 0 | 74 |
| no_feedback | 10 | 20 | 0 | 0 | 88 |

Comparable scored single/multi pairs: 7 of 30.
Multi wins: 0; single wins: 0; ties: 7.
Mean single-minus-multi weighted downtime: 0 weighted service-minutes (complete comparable pairs only).

Raw initial extraction micro-F1: 0.8557692307692307; metric-bearing run records: 122.
Labels cover recognized fixture sentences, not an independently audited natural-language dataset.

Failures and exclusions remain in the JSON report. Repetitions are not independent new scenarios. Applied action holds are not proof of better restoration. Actual API charges were not measured. No multi-agent superiority claim is made.

Wall times include concurrent batch contention and must not be presented as an isolated latency benchmark.

Source fingerprint: `6b9e380555eab3b8944dd56347bb4f935be03d585b46caff6d8f131fd95e97c0`.

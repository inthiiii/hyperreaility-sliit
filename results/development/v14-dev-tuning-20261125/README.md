# v14 development tuning (25 Nov 2026)

Development cases only (DEMO-005 + DEV-001…010, evidence v3), one repetition, `gpt-6-luna`,
Responses API, reasoning `none`, whole-run caps of 12 calls / 24k input / 4.8k output tokens / 180 s. Not an evaluation.

## Before tuning (`run1/`)

| Variant | Completed | Escalated | Median weighted downtime (completed) | Initial fact F1 | Mean input tokens |
|---|---:|---:|---:|---:|---:|
| multi | 11 | 0 | 6,480 | 0.97 | 11,268 |
| single | 7 | 4 (all whole-run token budget) | 5,760 | 0.98 | 13,615 |
| heuristic / CP-SAT | 0 | 11 (old rule: unknowns escalated) | — | — | 0 |

## After tuning (`run2-tuned/`)

| Variant | Completed | Escalated | Median weighted downtime | Initial fact F1 | Mean input tokens |
|---|---:|---:|---:|---:|---:|
| multi | 10 | 1 (Priority Assessor answer truncated, since fixed) | 6,480 | 0.97 | 10,595 |
| single | 10 | 1 (whole-run token budget) | 6,840 | 0.97 | 10,366 |
| heuristic | 11 | 0 | 7,200 | — | 0 |
| CP-SAT, no AI | 11 | 0 | 7,200 | — | 0 |

Per case (weighted downtime, lower is better):

| Case | CP-SAT, no AI | single | multi |
|---|---:|---:|---:|
| DEMO-005 | 6,480 | 5,760 | 5,760 |
| DEV-001 | 5,760 | 760 | 760 |
| DEV-002 | 8,640 | 5,040 | 5,040 |
| DEV-003 | 15,840 | 12,720 | 12,720 |
| DEV-004 | 16,560 | 13,440 | 13,440 |
| DEV-005 | 7,200 | 7,200 | 7,200 |
| DEV-006 | 5,760 | escalated | 5,760 |
| DEV-007 | 0 | 0 | 0 |
| DEV-008 | 6,480 | 6,480 | escalated |
| DEV-009 | 9,360 | 7,800 | 7,800 |
| DEV-010 | 16,560 | 9,250 | 9,250 |

## What this shows (development only)

- **Reading the reports matters.** Without agents, CP-SAT cannot use free-text evidence, and downtime is higher on 8 of 11 cases.
- **Single vs multi:** identical downtime on every case both completed. The difference so far is completion within the same budget. Before tuning, single exhausted its token budget on 4 of 11 cases because its one context grows each round.
- **Injection:** in every case that contained a prompt-injection report, it was flagged and not followed.

## Changes made from these observations

1. Rules about subtree outages, not inferring unstated facts, complaints not being asset claims, and holds needing evidence.
2. A non-actionable "revise" becomes notes for the human.
3. Baselines plan around unknowns and get scored.
4. The specialist output cap is raised to 650 tokens, and a failing advisory specialist is recorded without stopping the run.

Changes 1–3 were made between run1 and run2; change 4 was made after run2. EVAL2 cases were not run.

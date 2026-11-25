# Held-out benchmark report: evaluation-v3-run1

Model `gpt-6-luna` · 20 cases · 360 attempts · freeze `524945f`.

Synthetic, script-generated cases (evidence v3); not independently human-reviewed. Downtime is weighted service-minutes over 720 minutes, measured by the independent simulator (lower is better).

## Reliability, extraction, safety and usage

| Variant | Completed | Escalated | Failed | Fact F1 (initial → after review) | Distractor claims / run | Injection followed / runs | Calls | Input tok | Output tok | Seconds |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| heuristic | 60/60 | 0 | 0 | — | — | 0/0 | 0.0 | 0 | 0 | 0.0 |
| multi | 54/60 | 6 | 0 | 0.88 → 0.88 | 0.04 | 0/33 | 4.9 | 13,323 | 1,214 | 17.8 |
| no_feedback | 49/60 | 11 | 0 | 0.93 → 0.93 | 0 | 0/28 | 4.3 | 11,691 | 992 | 15.9 |
| no_reviewer | 60/60 | 0 | 0 | 0.94 → 0.94 | 0 | 0/36 | 3.3 | 8,657 | 777 | 12.3 |
| optimizer | 60/60 | 0 | 0 | — | — | 0/0 | 0.0 | 0 | 0 | 0.1 |
| single | 53/60 | 7 | 0 | 0.96 → 0.95 | 0.02 | 0/33 | 2.3 | 11,316 | 954 | 11.9 |

## Paired downtime comparisons (per-case medians)

| A vs B | Cases | A better | Tie | B better | Mean A−B | 95 % CI (bootstrap over cases) | Median relative change (all cases with B > 0, ties included) |
|---|---:|---:|---:|---:|---:|---|---:|
| multi vs single | 19 | 2 | 15 | 2 | -198.9 | -596.3 to 56.8 | 0.0 % |
| multi vs optimizer | 20 | 13 | 7 | 0 | -2,377.8 | -4,044.0 to -981.2 | -12.5 % |
| single vs optimizer | 19 | 11 | 8 | 0 | -1,810.5 | -3,333.7 to -636.3 | -12.0 % |
| multi vs no_reviewer | 20 | 1 | 17 | 2 | -32.8 | -192.8 to 72.0 | 0.0 % |
| multi vs no_feedback | 19 | 0 | 17 | 2 | 33.2 | 0.0 to 90.0 | 0.0 % |
| optimizer vs heuristic | 20 | 0 | 20 | 0 | 0 | 0 to 0 | 0.0 % |

## Per case (median weighted downtime; completed repeats in brackets)

| Case | heuristic | multi | no_feedback | no_reviewer | optimizer | single |
|---|---:|---:|---:|---:|---:|---:|
| EVAL2-001 | 13,680 (3) | 1,235 (3) | 1,235 (3) | 1,235 (3) | 13,680 (3) | 1,235 (3) |
| EVAL2-002 | 3,600 (3) | 450 (3) | 450 (3) | 450 (3) | 3,600 (3) | 450 (3) |
| EVAL2-003 | 5,040 (3) | 3,990 (2) | 3,990 (2) | 3,990 (3) | 5,040 (3) | 3,990 (3) |
| EVAL2-004 | 3,600 (3) | 3,150 (2) | 2,700 (3) | 2,700 (3) | 3,600 (3) | 2,700 (3) |
| EVAL2-005 | 16,560 (3) | 13,410 (3) | 13,410 (3) | 13,410 (3) | 16,560 (3) | 13,410 (3) |
| EVAL2-006 | 16,560 (3) | 14,940 (3) | 14,940 (1) | 14,940 (3) | 16,560 (3) | 14,940 (3) |
| EVAL2-007 | 12,960 (3) | 11,400 (3) | 11,400 (3) | 11,400 (3) | 12,960 (3) | 11,400 (3) |
| EVAL2-008 | 14,400 (3) | 12,150 (3) | 12,150 (3) | 12,150 (3) | 14,400 (3) | 12,150 (3) |
| EVAL2-009 | 720 (3) | 720 (2) | 720 (3) | 720 (3) | 720 (3) | 720 (3) |
| EVAL2-010 | 3,600 (3) | 475 (3) | 475 (3) | 475 (3) | 3,600 (3) | 3,600 (3) |
| EVAL2-011 | 7,920 (3) | 7,920 (3) | 7,920 (3) | 7,920 (3) | 7,920 (3) | 7,920 (2) |
| EVAL2-012 | 3,600 (3) | 3,600 (3) | 3,600 (3) | 3,600 (3) | 3,600 (3) | 3,600 (3) |
| EVAL2-013 | 0 (3) | 0 (2) | 0 (2) | 0 (3) | 0 (3) | 0 (2) |
| EVAL2-014 | 0 (3) | 0 (3) | 0 (2) | 0 (3) | 0 (3) | 0 (3) |
| EVAL2-015 | 15,120 (3) | 15,120 (3) | 15,120 (3) | 15,120 (3) | 15,120 (3) | 15,120 (3) |
| EVAL2-016 | 3,600 (3) | 3,600 (3) | 3,600 (3) | 3,600 (3) | 3,600 (3) | 3,600 (3) |
| EVAL2-017 | 4,320 (3) | 4,140 (2) | 3,960 (1) | 3,960 (3) | 4,320 (3) | 3,960 (3) |
| EVAL2-018 | 3,600 (3) | 3,150 (3) | 3,150 (3) | 3,150 (3) | 3,600 (3) | 3,150 (3) |
| EVAL2-019 | 13,680 (3) | 4,930 (2) | — (0) | 6,215 (3) | 13,680 (3) | 6,215 (1) |
| EVAL2-020 | 14,400 (3) | 5,025 (3) | 5,025 (2) | 5,025 (3) | 14,400 (3) | — (0) |

## Reading this report

- Escalated and failed attempts are not scored; a variant that completes fewer cases is compared only on cases where both have a median.
- The proposal target (≥ 10 % median paired downtime reduction for multi vs single) is assessed from the table above; no superiority claim is made unless the interval excludes zero in the multi-agent direction.
- Raw attempts: `attempts.jsonl`; traces: `runs/`; simulator outputs: `simulations/`.

# Benchmark simulator-scoring fix

The existing benchmark runner previously emitted `actual_weighted_downtime=null`
and `pending_independent_simulator` for every run. It now passes each valid plan
through the independent IncidentEpisode evaluator and records actual service
metrics only after the original incident horizon completes.

This change is the scoring gap fix only. It does not establish a fair hosted
single-/multi-agent comparison, validate held-out cases, perform live inference,
run a participant study, or claim multi-agent superiority. Those are later gates.

## Run an offline engineering check

From the repository root, with the project virtual environment activated:

```bash
python -m project.evaluation.runner \
  --scenarios data/processed/agent_inputs/demo/DEMO-005.json \
              data/processed/agent_inputs/development/DEV-010.json \
              data/processed/agent_inputs/development/DEV-006.json \
              data/processed/agent_inputs/development/DEV-008.json \
  --output results/local_benchmarks/scoring-check-new \
  --variants heuristic optimizer --repeats 1
```

Choose a new output directory for each experiment; existing manifest/output files
are never overwritten. Default truth comes from data/evaluation/ground_truth;
`--data-root /path/to/release/data` selects another explicitly supplied release.
The initial visible input must match its registered case content, not merely its
scenario ID, before it can be paired with evaluator truth. Unknown/missing truth
or changed input becomes a retained failed attempt, never an invented zero score.

## Outputs and semantics

- manifest.json: source fingerprint, input hashes, variants/repetitions, order seed,
  package versions and whole-incident limits.
- attempts.jsonl / attempts.csv: every attempted case/variant/repetition, status,
  recorded model usage, runtime and measured scores when complete.
- runs/: original core run traces; no evaluator truth is added to core inputs.
- simulations/: explicit automated benchmark approvals, independent result/state
  hashes, and each episode's actual output. This is not a real human approval.
- summary.json: scored, escalated, failed and incomplete counts.

| Status | Scoring status | Primary downtime value |
|---|---|---|
| completed | scored | Independent full-horizon measurement |
| escalated | not_scored_escalated | null |
| failed | not_scored_failed | null, with phase and error type |
| incomplete | not_scored_episode_limit | null; prefix artifact retained |

`actual_weighted_downtime` and weighted availability use weighted service-minutes.
Unweighted availability/downtime use service-minutes; critical downtime uses
critical service-minutes; first restoration is incident minutes and remains null
if none occurs. End-of-horizon availability and unmet needs count services.
`api_cost` remains null because pricing/charges were not measured. Missing provider
usage is flagged incomplete, not silently counted as zero tokens.

A paused incident retains the same evaluator instance and accumulated intervals.
Only its reached visible checkpoint enters a fresh coordinator. The harness
requires a higher state version and creates a new explicitly automated approval
before resuming. Full-horizon identity and weighted-minute accounting are checked
before publishing the final score. Prefix/null, non-finite, mismatched or
unbalanced results cannot become successful scores.

Whole-incident caps remain 12 calls, 24,000 input-token reservations, 4,800 output
reservations and 180 seconds across all replans. New episode clients receive only
the remaining budget. Cleanup errors are recorded without losing the attempt or
aborting later jobs. Hosted variants still require --allow-live and valid local
configuration; no real API calls were made for this change.

## Actual validation

Full test suite: **364 passed** in 34.79 seconds. Thirteen additional scoring tests
cover static and dynamic measurements, escalation, missing truth/input mismatch,
prefix limits, invalid/non-finite output, complete-horizon accounting, aggregate
budgets, model usage and cleanup failure retention.

Offline CLI smoke: eight attempts, four scored, four expected evidence escalations,
zero failures/incomplete jobs, zero model calls. Fixture results:

| Case | Variant | Weighted downtime | Approved episodes |
|---|---|---:|---:|
| DEMO-005 | heuristic | 5760 | 1 |
| DEMO-005 | optimizer | 5760 | 1 |
| DEV-010 | heuristic | 9950 | 2 |
| DEV-010 | optimizer | 9250 | 2 |

DEV-006 and DEV-008 escalate for both variants and remain unscored. These are
engineering fixtures, not the planned held-out comparison or evidence about
hosted agent performance. Formal baseline fairness, model selection, cost
measurement and independent evaluation review remain unchanged pending approval
of this checkpoint.

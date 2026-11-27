# Ihthisham core implementation

Date: 22 November 2026. Source baseline: setup merge a2f7bee. Work implemented in the isolated `relink-core` checkout on `feature/core-planner`; user checkout retains its original working tree.

## Files

Core: schemas, state resolver, validator, greedy/CP-SAT planner, coordinator/approval and demo runner. Hosted adapter: project/llm/client.py. Offline fixture parser: project/agents/extraction.py. Tests and visible development fixtures: tests/core. Interfaces and limitations: docs/DATA_CONTRACT.md and docs/CORE_IMPLEMENTATION.md.

## Actual verification

Python 3.11.18, using the existing project environment (Pydantic 2.14.4, OR-Tools 9.15.6755, NetworkX 3.6.1, OpenAI SDK 3.57.0). Final core suite: 49 tests passed in 4.94 seconds. All 31 starter input JSON files passed schema compatibility checks. Additional 16 to 19 site static scenarios produced valid schedules under independent checking; solver status was OPTIMAL for these development examples. No hosted API call or spend. SDK request parameter presence checked locally. Template demo produced an awaiting-approval plan, one S02 generator deployment and zero model calls. Predictions match the hand-calculated static example; no independent simulation or benchmark was run.

## Reproduce

```sh
source .venv/bin/activate
python -m pytest tests/core -q
python -m project.core.demo --scenario tests/core/fixtures/DEMO-005.json --mode template --output /tmp/relink-core-demo.json
```

## Next integrations

Publish the shared models first. Zahra imports ScenarioInput/SimulationResult and supplies evaluator isolation, event execution and metrics. Eyaas should use CoreSession with a fresh Coordinator for every Prepare operation; approve_run is the reviewed-run approval gate. Operator-confirmation reports must be recorded before evidence is resolved; clients must rebuild a new state version after material changes. Never mutate an approved object in place expecting its approval to survive.

Completed at the 23 November checkpoint: persistent traces, session/approval boundary, preflight and benchmark infrastructure. Required follow-up: authenticated operator identity, full future-event lifecycle and independent restoration evaluation. Exact model ID is intentionally unset until the user selects/tests a hosted model. Some transport environments may require optional SOCKS dependencies; no live provider transport was validated here.

## AI disclosure

Source and tests were created with ChatGPT/Codex assistance. Fixture parser is deterministic and narrowly scoped. Fake adapter responses verify orchestration only. Do not count them as real model results or claim four-agent superiority without the planned paired evaluation.


## 23 November pre-merge checkpoint

Full suite: **69 passed**. Offline CLI: awaiting_approval, one action, zero model calls. Paired heuristic/optimizer development smoke: two attempts, both awaiting_approval; actual restoration scores deliberately absent pending Zahra's simulator. Live model inference was not performed: the original local environment contains a key but no exact model ID. New tests exercise trace integrity/redaction, failed-run retention, stale approval, repeat execution, failed replacement, scheduling feedback, specialist reassessment, ablations and benchmark guards.

Read `docs/PREMERGE_CHECKPOINT.md` next. The writable checkout is an update source; apply its patch to the Documents repository, test there, then commit/push your own branch. Do not count fake-client tests or these development fixtures as held-out model evaluation.

## Benchmark scoring gap fix (24 November; review checkpoint)

The benchmark runner now scores validated plans through the independent incident
evaluator, including fresh-approved continuation after resource loss. This
supersedes earlier notes that benchmark restoration scores were absent. Input/truth
binding, complete-horizon checks, separate escalation/failure/incomplete statuses,
episode artifacts and aggregate budgets are covered by regression tests. Full
suite: 364 passed. Offline CLI smoke: eight attempts, four scored and four expected
evidence escalations, zero model calls. See ../BENCHMARK_SCORING.md for exact
commands and fixture outcomes. No live inference, formal baseline-fairness changes
or remaining implementation steps were performed in this checkpoint.


## Priority Step 2 — operator clarification (24 November)

The joint core/dashboard integration now records explicit operator fact confirmation,
retains original reports and auditable corrections, advances state versions, clears
stale plans/approval, and requires separate replanning and approval. History exposes
confirmation records. The independent evaluator preserves its physical truth and
same-incident continuation metrics. See [operator confirmation](../../OPERATOR_CONFIRMATION.md)
for workflow, regression coverage and remaining identity/verification limits.
This checkpoint supersedes earlier statements that operator clarification was absent;
live hosted-model evaluation remains a later priority.

## Priority Steps 3 and 4 — combined hosted/fairness checkpoint

Implemented the matched four-stage hosted workflow, actionable conservative
agent requests, raw extraction scoring, model/configuration drift checks, paired
comparison artifacts and bounded live-check command. The dashboard surfaces
action deferrals before separate operator approval. This is Ihthisham's
workstream; no new teammate co-author is attached.

Offline CLI: four baseline attempts (DEMO-005 and DEV-010, heuristic/optimizer),
all scored by the independent evaluator. DEV-010 retains its two-approval
continuation semantics. No live provider request was made: an exact OpenAI
model ID is still required. See [HOSTED_FAIRNESS.md](../../HOSTED_FAIRNESS.md).

Full regression at this checkpoint: **411 passed in 42.65 seconds**.

## Joint live Luna completion checkpoint — 24 November

Selected `gpt-6-luna`, reasoning `none`, Responses API with exact input counting.
Both hosted demo workflows and the real dashboard approval/simulation path are
verified. Final full regression: **428 passed in 43.08 seconds**.

The final matched-workflow-v4 cohort has 10 development cases × 3 repeats ×
4 variants = 120 attempts: 61 scored incidents and 59 escalations. Raw labelled
fixture extraction micro-F1 was 100% in each variant; the metric excludes
unlabelled reports and does not establish independent natural-language accuracy.
Eleven comparable single/multi pairs all tied; no restoration superiority claim.
A separate real permit challenge changed the validated candidate through a typed
resource hold, but its reviewer escalated, so it was not approved/simulated.

Earlier rounds and failures are retained. See [Luna validation](../LUNA_LIVE_VALIDATION.md)
for current results, traces, limitations and reproduction. Joint co-author credit
is requested for all four team members. Independent case review and final
release/participant evidence remain later priorities.


## Priority 3–4 follow-up — 25 November

Completed strict hosted schemas with valid evidence-ID constraints, lossless
context compaction, bounded review clarification, fresh review after every new
hold, retained rejected-output audit, and visible-state arithmetic/service
forecast tools. Regression: **458 passed in 43.87 seconds**. Both workflow modes
retain equal context/tools and unchanged aggregate incident caps. See
[the completion update](../PRIORITY_3_4_COMPLETION.md) for live outcomes and all
remaining quality limits. Follow-up credit includes Ihthisham, Zahra, Eyaas and
Kiruthika; work was prepared with ChatGPT/Codex in Ihthisham's session.

Stop before Priority 5–7 and leave the pull request for review.


Final current-source v13 development comparison: 120 attempts (10 cases ×
3 repeats × 4 variants), 57 full-horizon scores and 63 escalations. Full multi
completed 12/30 versus single 16/30. All 12 comparable scored pairs tied; no
restoration advantage. Raw recognized-fixture extraction F1 is 100%, with the
coverage limits in the completion document. Implementation is delivered;
operational reliability still needs improvement. Stop before Priority 5–7.

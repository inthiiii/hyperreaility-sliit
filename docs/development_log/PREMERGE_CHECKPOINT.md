# Core checkpoint before teammate merges

Date: 23 November 2026. Baseline: core commit `2b6e4fb` on `feature/core-planner`.

## Ready now

- Versioned incident contracts, conservative state resolution, greedy/CP-SAT planning and independent schedule validation.
- Hosted single/multi-agent orchestration, bounded feedback and recorded review ablations.
- Private, atomic run JSON with SHA-256 integrity check, structured failure metadata, model usage and prompt/schema fingerprints. `project.core.tracing.read_run` verifies the record. Credential-pattern redaction is not a general personal-data anonymizer; use synthetic/redacted incidents.
- Operator approval tied to the reviewed run and exact plan/state hashes. A failed prepare revokes prior session state. A fresh Coordinator is required per run.
- Local model configuration preflight; no inference, model discovery or automatic model choice.
- Paired benchmark infrastructure: seeded job order, input/source hashes, package versions, every attempt retained, CSV/JSONL outputs. No restoration or financial scores until independent simulation is connected.

## Verify locally

```sh
source .venv/bin/activate
python -m pytest -q
python -m project.core.demo --scenario tests/core/fixtures/DEMO-005.json --mode template
python -m project.llm.health
python -m project.evaluation.runner --scenarios tests/core/fixtures/DEMO-005.json --output results/local_benchmarks/checkpoint-01 --repeats 1
```

Expected tests: 69 pass. Demo: awaiting_approval, one action, zero model calls. Preflight exits 2 when model/key configuration is missing, and 0 when configured; configured does not mean transport/model availability is verified. Benchmark: two attempts, scoring pending. Use a new output directory each time; existing experiments cannot be overwritten.

To enable later hosted testing, set the exact `LLM_MODEL` locally in `.env` and rerun preflight. Then `python -m project.core.demo --scenario tests/core/fixtures/DEMO-005.json --mode single` makes real paid requests; multi mode uses more requests. Budget reservations deliberately fail closed and may stop larger inputs or revisions. Never commit credentials or local run records. Hosted benchmarks additionally require `--allow-live`; freeze settings and use the same visible cases, tools and limits across comparisons.

## Eyaas integration

```python
from project.core.coordinator import Coordinator
from project.core.integration import CoreSession

session = CoreSession()  # Persist once per dashboard user session.
result = session.prepare(Coordinator(trace_dir="results/local_runs"), scenario)
# Display result.reasons; allow Approve only for awaiting_approval.
approval = session.approve(operator_id="actual-operator-identity")
# session.simulate() raises IntegrationNotReady until Zahra's callback is supplied.
```

Create a hosted adapter explicitly only after a user Prepare action, pass it to a fresh Coordinator, and close it afterward. Never create API calls on dashboard rerenders. The returned run is logged before operator approval; the dashboard must retain/display the approval separately and record the operator decision in its audit history. Do not use the low-level `approve` function on a candidate from an escalated run. `CoreSession` is an in-process integration boundary, not authentication or a durable transaction service.

## Zahra integration

Supply a pure callback `simulate(verified_state, plan)` to `CoreSession(simulator=callback)`. The adapter should call Zahra's independent evaluator and return the agreed SimulationResult. It must not mutate passed inputs or dispatch real equipment. Hidden truth and future events remain in the evaluator only. Do not let agents inspect them. In-process duplicate execution is blocked after successful return; persisted/idempotent execution across process restarts is later integration work.

Agree on generator expiry, event timing, restoration definition, metrics and next observed snapshot before connecting event-driven replanning. A new snapshot needs a new state version and approval; restarting planning does not represent continuing already-started jobs. Do not run a fresh static plan in the middle of ongoing work without implementing that lifecycle.

## What Ihthisham can stop at

Apply this update, test, commit/push and open the core PR. Then wait for Zahra's loader/simulator and Eyaas's dashboard PRs. Do not duplicate their implementation. Select a hosted model locally when ready; live inference is still unverified. After teammate merges: wire the real interfaces, add end-to-end lifecycle tests, freeze held-out cases, run paired hosted experiments, and replace predicted values with independently measured outcomes. Reviewer and feedback ablations are experiments, not evidence of multi-agent superiority.

## Recorded checks

69 tests passed on the existing Python 3.11 project environment. Offline demo and two-attempt baseline benchmark completed. Failure/approval/trace integration tests use fake simulator/model callbacks, not teammates' unmerged implementations. General free-text evidence grounding, authenticated identity, real hosted transport, dynamic execution and independent scoring remain unvalidated.

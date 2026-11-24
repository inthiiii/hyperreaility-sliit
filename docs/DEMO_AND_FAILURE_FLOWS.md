# Operator walkthrough and failure-flow checkpoint

This checkpoint adds read-only workflow guidance to Overview, Planning and Results.
The panel derives its state from the active run, recorded decision, matching
simulation outcome and attempt records. It does not generate plans, grant
approval, run simulations, alter evidence or initialize a hosted model.

## Walkthrough on current data-only main

Run `python -m streamlit run project/main.py` from an activated environment.
Use **Offline template baseline** with **CP-SAT optimizer** for these checks.
Template extraction is a deterministic baseline, not a hosted multi-agent demo.

| Case | Actions | Expected result |
|---|---|---|
| DEMO-005 normal planning | Enter operator label, generate plan, inspect schedule/evidence, approve | Awaiting simulator until the backend merges; no fabricated measured outcome |
| DEV-006 conflict | Select scenario and generate | Clarification required; reasons and evidence visible; approval/simulation disabled |
| DEV-008 missing evidence | Select scenario and generate | Uncertainty retained; clarification required; approval/simulation disabled |
| Rejection | Generate DEMO-005, reject with review note | Rejected plan cannot be approved or simulated; start a new explicit attempt |
| Explicit retry | Click Start a new attempt, then Generate plan | New run; prior plan/approval/results removed; no automatic retry |
| Scenario change | Approve DEMO-005, then select DEV-006 | Fresh session state; no carried-over plan, approval or current outcome |
| Unsupported simulation | Backend reports IntegrationNotReady | Episode support pending; no result published; attempt stored once; no automatic rerun |

Unsupported-path UI tests inject a clearly labeled exception callback. They prove
UI behavior only, not implementation of dynamic simulation. No test callback is
available as a selectable production/demo mode.

## Normal measured recovery after backend integration

The preceding static-integration checkpoint supplies real-engine tests and a
Streamlit click-flow test. Once Zahra's loader/evaluator/engine are merged, use
DEMO-005: generate, approve, simulate, open Results. Expected: V02 and V04 available
on [30,150), weighted available minutes 720, weighted downtime 5760 and first
restoration minute 30. Inspect action outcomes and export the audit record.

While the backend is absent, these tests skip explicitly. Do not describe a
skipped engine test as a successful simulator run. Dynamic continuation and the
horizon-boundary fix remain with Zahra. No backend source files change here.

## Verification and manual rehearsal

```bash
python -m pytest tests/ui/test_demo_flows.py -q
python -m pytest -q
```

Seven new tests cover real conflict/missing-data escalation, rejection and retry,
backend-pending/expired approval, unsupported-attempt deduplication, and two
Streamlit interaction walkthroughs. Existing static-engine integration coverage
is retained. Use DEMO_QA_CHECKLIST.csv for manual rehearsal; manual entries begin
as NOT RUN and must be updated only after someone actually performs the steps.

The workflow panel is guidance, not a permission mechanism. The existing review,
source freshness, validator, approval binding and audit checks remain the
execution boundary. Hosted inference, independently audited held-out evaluation,
and production operator authentication are separate work.

## Completion update: event-capable backend

The earlier data-only/backend-pending instructions above describe the previous
checkpoint. On feature/zahra-completion the real backend is present. DEMO-005 now
produces measured static results. DEV-010 stops at minute60: inspect its prefix
result, return to Planning, choose Accept event update and replan, generate a new
plan and approve it, then simulate to finish the same incident at720. Full-horizon
metrics stay null at the pause. The completed fixture reports weighted available
minutes7310 and downtime9250; no new approval is inherited from history.

Both static and dynamic browser rehearsals were performed on the completion
checkout by Codex. These are synthetic local tests, not independent human QA.
The optional note field now clears on an explicit new attempt/event update.

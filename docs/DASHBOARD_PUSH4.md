# Dashboard Push 4 — operator decisions and simulation boundary

Date: 23 November 2026. Branch: `feature/dashboard`. Baseline: Push 3 commit `cafa599`.

## Available now

- A valid, non-escalated plan can be approved or rejected by an explicitly labelled operator, with an optional note.
- Decisions record operator label, timestamp, run/scenario IDs, input hash, plan/state hashes, exact display binding, note and the content-bound Approval object.
- Private, atomic records with checksums are written before a new decision becomes active. Write failure leaves no new approval active. These checksums detect changes; they are not signatures or authenticated identity.
- Rejection revokes an existing approval. A rejected plan cannot subsequently be approved; generate a new plan. Duplicate decisions do not create duplicate records.
- Decisions bind the previously rendered plan through callback arguments. A changed plan/state, stale click, invalid schedule or escalated run cannot bypass backend checks.
- The selected allowlisted source file is rechecked on disk before decision/simulation, not just during page rerenders. A source change also prevents accepting an in-progress callback result.
- New planning attempts and scenario changes clear current decisions/approval/results. Decision history is retained in the current browser session and local audit files.
- Simulation requires matching active approval, the recorded operator label, a fresh display binding, a connected callback and no prior simulation attempt for that plan hash.

The operator label is a local-demo identity claim, not login/authentication. Approval authorizes simulation only; no live crew dispatch or network control exists.

## Simulator status — explicitly pending

**Zahra's independent simulator is not in this branch.** The application does not attach a fake implementation or reuse planner predictions as restoration outcomes. Simulation stays disabled with a visible pending-integration message even after approval.

`project/ui/simulation_service.py` supplies a synchronous callback boundary:

```python
from project.ui.simulation_service import attach_simulator

# Application integration code, once Zahra's independent backend exists:
attach_simulator(session, evaluator_callback, label="Independent evaluator · exact version")
```

`evaluator_callback(verified_state, plan)` receives deep copies of the approved visible objects and must return a SimulationResult or a compatible dictionary. This is a trusted backend integration function, not a dynamic import or user-upload feature. CoreSession checks approval before invoking it. If Zahra's evaluator also expects an Approval argument, a backend adapter must supply a copy of the current content-bound approval. Hidden truth/future events stay inside that evaluator/adapter; do not put them in dashboard tables or agent contexts.

The boundary checks scenario/plan/state-version identity, completed-action IDs and finite numeric metrics. This validates the interface, not the evaluator's physical model or metric accuracy. Zahra's independent evaluation tests remain necessary.

Simulation attempt metadata is persisted before callback execution; failure to save the start record prevents execution. After successful output validation and a second source/approval check, the result is persisted and exposed as the current typed result. Failed/invalid attempts retain a safe error type and are not automatically retried. Repeated clicks or rerenders never execute the same plan hash twice within this session. Investigate failures and generate a fresh plan before trying again. Cross-process durable exactly-once execution is not implemented.

A scenario switch deliberately disconnects its evaluator callback. Application integration must attach the callback for the newly selected scenario, so an old scenario's hidden-world closure is never silently reused. New planning attempts on the same scenario preserve the attached callback but revoke approval and current results.

## Local records

All paths below are under the existing ignored local-run root:

- `results/local_runs/decisions/<decision_id>.json`
- `results/local_runs/simulation_attempts/<attempt_id>.json`

Records use versioned payload/checksum envelopes and private file permissions. `project.ui.local_records.read_record` verifies integrity. Do not restore active approvals automatically from these files; they are history, not authenticated authorization. Review notes/operator labels are not generally anonymized by credential-pattern redaction. Use synthetic or appropriately authorized/redacted data.

## Verify manually

Stop/restart Streamlit after installing the update so sessions use the new fields.

```sh
source .venv/bin/activate
python -m pytest -q
python -m streamlit run project/main.py
```

1. Choose DEMO-005 → Planning → Offline template baseline → Generate plan.
2. Confirm approval is disabled without an operator label.
3. Enter your operator label in the sidebar, inspect the schedule/evidence/validation and optionally enter a note.
4. Approve: expect a recorded approval, duplicate approval disabled and simulation still disabled because the real evaluator is missing.
5. Reject: expect approval revoked, a rejected-plan message and no ability to approve that same run.
6. Start a new attempt and generate again: expect a new review and no old approval/results.

## Actual verification

**146 tests passed**, including **77 UI/service checks**. The 29 new review checks cover private decision persistence, checksums/tampering, duplicate and terminal rejection, labels/notes, stale bindings, post-approval mutation, escalated/invalid plans, audit failures, source changes on disk, reset/history behavior, absent simulator, matching operator/approval, callback copies, exactly one in-session callback attempt, invalid IDs/non-finite outputs, safe callback errors and UI callbacks.

Simulator tests use explicitly injected test-only callbacks with a test marker, not restoration metrics. No test callback is attached by the application. Browser QA generated the real offline schedule, entered a test operator/note, recorded approval, confirmed pending simulation, then rejected the plan and observed revocation. No paid API request or real independent restoration simulation was performed.

## Remaining work

Push 5 provides run/decision history and measured-outcome presentation. Actual simulator wiring/scoring waits for Zahra's implementation and end-to-end validation. Authentication, dynamic execution/replanning, held-out hosted experiments and final demonstration remain integration work. Keep the dashboard PR open while the remaining agreed pushes are completed; no force-push or main-branch mutation is needed.

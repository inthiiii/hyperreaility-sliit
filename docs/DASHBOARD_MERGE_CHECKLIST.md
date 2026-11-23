# Dashboard merge checklist and follow-up

Date: 24 November 2026. Scope: dashboard Pushes 1–5 on feature/dashboard.

## Ready to review and merge

- Scenario selection, synthetic dependency diagram, evidence/resource/policy inspection.
- Explicit offline/hosted planning integration, real schedules/validation and duplicate-request guards.
- Recorded operator approval/rejection, content/display/source binding and stale protection.
- Typed, approval-gated simulator callback with explicit pending state; no application-installed mock evaluator.
- Read-only history, record checks, CSV/JSON downloads and evaluator-output views.
- Verified source update: 161 automated tests pass. Review required GitHub checks separately; local checks do not establish their status.

After applying Push 5, restart/inspect the application, review the staged diff and commit/push. Review the existing PR into main, resolve any conflicts with newer main changes and run affected tests. Merge after review and required checks. A normal merge commit preserves the individual push commits; no force push or history rewrite is needed. If using squash, review its final message/attribution rather than assuming every original message will be retained.

After the remote PR merge:

```sh
git switch main
git pull --ff-only origin main
```

## Suggested PR title

Build operator dashboard with planning review and history

## Suggested PR description

Adds a Streamlit operator dashboard for synthetic telecom incidents: validated scenario selection, dependency/evidence/resource views, explicit core planning, recorded human decisions, approval-gated simulator boundary, read-only run/decision history and evaluator-output presentation/exports. Browsing and history inspection never invoke models or restore approvals.

Validation: 161 automated tests pass; browser checks cover the real offline schedule, human approval/rejection, history and pending results. Hosted tests and simulator-boundary tests use explicitly injected clients/callbacks. No paid inference or real independent restoration evaluation was performed.

Integration remaining: Zahra's independent loader/simulator, actual metric and trajectory verification, dynamic execution/replanning and live hosted evaluation. The application includes no fake evaluator; results remain pending until real simulation is integrated. This PR completes the dashboard interface workstream, not the full evaluated MVP.

## Required follow-up before the full MVP is complete

1. Merge Zahra's data/loader and independent evaluator, respecting visible-input/hidden-truth isolation.
2. Attach the backend callback for each selected scenario; confirm exact result metric/time/trajectory fields and units.
3. Verify approved end-to-end execution, generator expiry, events and preserved history. Build the remaining dynamic lifecycle before claiming replanning works.
4. Configure/freeze the exact hosted model and run real development smoke tests and matched held-out experiments. Keep failures and negative findings.
5. Reconcile docs, disclosures, dependencies and actual findings; make a clean-install check and actual-execution video.

Do not claim measured downtime reduction, real operator integration, authenticated approvals or production readiness from the dashboard merge alone.

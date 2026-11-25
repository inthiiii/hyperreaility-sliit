# Demo and failure-flow walkthrough

Run from the repository with the existing environment activated:

```sh
python -m streamlit run project/main.py
```

The simulator is integrated. Use **Offline template baseline** and **CP-SAT
optimizer** for repeatable recovery demonstrations; this mode makes no model
requests. It is a deterministic baseline. The hosted multi-agent mode is separate.

## Static recovery

1. Choose DEMO-005. With the operator label blank, generate a plan and observe
   that approval and simulation are disabled.
2. Enter a demo operator label; inspect Schedule, Evidence and Agent activity.
3. Approve the current plan, then click Simulate approved plan once.
4. Open Results: horizon720, weighted available720, weighted downtime5760,
   first restoration30. V02 and V04 are available on [30,150).
5. Open History to inspect/export the record. Reloading never restores approval.

## Dynamic recovery

1. Choose DEV-010, generate offline, inspect and approve, then simulate.
2. The incident pauses at minute60. Results cover only the elapsed prefix;
   full-horizon availability/downtime are null. Inspect or download that result.
3. Return to Planning; click Accept event update and replan. The old plan and
   approval clear while committed work and elapsed service are preserved.
4. Generate a new plan, inspect it, approve again, then simulate to finish.
5. At minute720, weighted available7310 and downtime9250. Simulation is disabled
   after completion; rerendering does not repeat execution.

## Failure and review flows

| Case | Action and expected result |
|---|---|
| DEV-006 | Generate offline: contradictory equipment evidence escalates; no approval/simulation |
| DEV-008 | Generate offline: missing equipment fact stays unknown; no approval/simulation |
| Clarification | An empty submission fails. For synthetic testing only, explicitly label the development fixture as the source; select the confirmed boolean and acknowledge verification. Regenerate before approval. Real use requires real verified evidence. |
| Rejection | Enter a note and reject DEMO-005. Rejected plan cannot execute. Start a new attempt: note blank, old approval gone; explicitly generate and approve the replacement. |
| Scenario change | Approve then change incident: previous plan, approval and results clear |
| History | Opening an old approved plan/result is read-only and cannot grant current authorization |
| Unsupported backend | Automated injected exception test only; result not published, no automatic retry. No production selector exposes this callback. |

## Hosted demonstration

Settings should show the configured provider/model without displaying the key.
Select Hosted multi-agent workflow; generation sends synthetic incident data to
the configured service and may incur charges. Run only an explicitly bounded
smoke, inspect actual messages, and retain its actual outcome. Approval remains
required for a valid candidate. No silent offline fallback is permitted.

The 25 November smoke reached gpt-6-luna and escalated after three calls due to
an unnecessary specialist clarification. It did **not** demonstrate a successful
hosted restoration. Use the reproducible offline flows for recovery rehearsal
until that open issue is resolved; keep the hosted outcome visible in evidence.

See [Priority 6 results](development_log/PRIORITY_6_QA.md) and [checklist](development_log/DEMO_QA_CHECKLIST.csv).

```sh
python -m pytest -q tests/ui/test_demo_flows.py tests/ui/test_history_results.py tests/ui/test_dynamic_integration.py
python -m pytest -q
```

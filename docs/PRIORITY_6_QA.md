# Priority 6 — Application QA and demo rehearsal

25 November 2026. QA execution is complete; hosted happy-path readiness is **not** signed off.
Base: main at `6bec1976d78e0a65da3e770b06af4b52c18a27ef` (PR #13).

## Execution and attribution

Codex operated the actual local Streamlit interface in Ihthisham's session and
ran pytest. The operator label was `RELINK QA rehearsal`, a synthetic test label.
These results do not claim that Kiruthika or Eyaas personally performed the
walkthrough, or that independent human validation took place. Kiruthika Vijayakumar
and Eyaas Ajmal receive the requested Git co-author credit for this checkpoint;
credit is separate from tester identity. No human signature or evaluation review
worksheet was completed in this milestone.

Environment: macOS, existing project virtual environment, Streamlit on loopback
port 8520. Offline template extraction + real CP-SAT + independent simulator for
recovery measurements. One hosted multi-agent smoke request used OpenAI
`gpt-6-luna`, Responses API, reasoning `none`. The normal whole-run limits stayed
12 calls / 24,000 input / 4,800 output tokens / 180 seconds; solver ≤5 seconds.

## Observed outcomes

| Flow | Actual result |
|---|---|
| Empty operator label | Approval and simulation disabled |
| DEV-006 conflicting report | Clarification required; approval and simulation blocked |
| DEV-008 missing equipment fact | Unknown retained; approval and simulation blocked |
| Invalid clarification submission | Rejected until a boolean and verification acknowledgement were supplied |
| Explicit synthetic DEV-008 confirmation | Old candidate invalidated; new generation required; no inherited simulation approval |
| Reject → explicit retry | Rejected candidate terminal; replacement needs approval; stale note fixed and retested |
| Change incident after approval | Previous plan, approval and current result cleared |
| DEMO-005 complete episode | Horizon 720; weighted available 720; downtime 5,760; first restoration minute 30 |
| DEV-010 dynamic episode | Pause at minute 60; full-horizon prefix metrics null; second approval required; finish at 720 with available 7,310 and downtime 9,250 |
| Repeat simulation / reload / history | Completed simulation cannot rerun through the button; reload loses active authorization; saved history never restores it |
| Current hosted metadata in History | Previously skipped attempt now visible, explicitly unchecksummed |
| Catalog / configuration | Eleven demo/development choices only; model configured; no evaluation cases selectable |
| Hosted multi-agent smoke | Escalated after 3 calls, 20.37 seconds; no candidate; approval and simulation correctly blocked |

Recovery values are **weighted service-minutes**, with time points in incident
minutes. These are synthetic fixture outcomes, not a measured improvement over
another planner. Static rehearsal repeated successfully after the fixes.

## Defects and fixes

**QA-D01 — stale rejection note (fixed).** Starting a new attempt cleared the
Python key but Streamlit restored the previous frontend widget value. A prior
rejection reason could then be attached to a new approval. Explicitly assign the
empty string before rendering the note widget, including scenario change and
event continuation. Browser retest: enter `OLD QA NOTE MUST RESET`, reject,
explicitly retry, generate and approve; replacement note stays blank.
The Streamlit regression now exercises a non-empty rejection note and checks
the replacement decision note. The actual browser-generated
[replacement approval audit](qa/priority6-20261125/retry-decision.json) also
contains an empty note; its original local envelope checksum was verified.

**QA-D02 — valid hosted attempt hidden from History (fixed).** The strict reader
allowlist lagged behind the writer's API-mode, reasoning-effort and auxiliary
request fields. Accept these three known fields; require a list of dictionaries
for auxiliary records. Preserve unknown-field rejection, identity checks,
checksums and the unchecksummed metadata label. Browser search for `b1906ca2`
now finds the original record. Tests reject malformed auxiliary records and
unknown additional fields.

**QA-D03 — unnecessary specialist clarification (open; hosted demo readiness).**
Run `4b3f3248-2a93-4bfd-9b33-0e9f96ea9664` reached all three initial specialists.
The service priority assessor set `clarification_required=true` and deferred both
generator options for human selection while its own finding said the objective
and timing permit comparison and no missing facts/policy conflict require
clarification. The coordinator honored the escalation. Recorded usage: 4,785
input tokens and 538 output tokens across three successful API responses.
No reviewer call, candidate, simulation or automatic retry followed. Keep this
as a failed hosted happy path and a passed fail-closed check. Before claiming a
reliable hosted demonstration, resolve the specialist contract/behavior using
development cases, test contradictory outputs, and repeat a bounded development
smoke. Do not suppress clarification or tune against frozen evaluation answers.

## Evidence and checks

- [Checklist](DEMO_QA_CHECKLIST.csv): individual outcomes and tester/method.
- [Before-fix observations](qa/priority6-20261125/browser-observations-before-fix.json)
  and [after-fix observations](qa/priority6-20261125/browser-observations-after-fix.json):
  actual recorded UI states. The download path was normalized for portability.
- [Measured results](qa/priority6-20261125/measured-results.json): three extracted
  result payloads; original local envelopes' checksums verified at export.
- [Downloaded prefix](qa/priority6-20261125/downloaded-prefix.json): actual browser
  download at the DEV-010 pause, with null full-horizon measurements.
- [Hosted smoke](qa/priority6-20261125/hosted-smoke.json): synthetic specialist
  messages and usage excerpt; provider request identifiers omitted.
- Screenshots: [static](qa/priority6-20261125/static-complete.jpg),
  [dynamic](qa/priority6-20261125/dynamic-complete.jpg),
  [history fix](qa/priority6-20261125/history-fixed.jpg),
  [hosted escalation](qa/priority6-20261125/hosted-escalation.jpg).

Focused regressions: **25 passed**. Full suite: **509 passed in 52.79 seconds**.
The existing v2 evaluation release validates with all twenty cases and its
203-file freeze unchanged. Its independent human review remains pending.
Unsupported-backend UI handling was checked by injected automated tests only;
there is no selectable unsupported callback in the real interface.

Scope: one desktop browser session, synthetic demo/development data and one
hosted smoke. This does not certify mobile layouts, cross-browser compatibility,
real network operation, independent human evaluation or hosted reliability.
Priority 7 final comparison/release has not started.

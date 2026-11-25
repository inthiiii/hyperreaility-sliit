# Dashboard Push 3 — explicit planning workflow

Date: 23 November 2026. Branch: `feature/dashboard`. Baseline: Push 2 commit `18d9ea7`.

## Implemented

The Planning page now calls the actual core through the per-user CoreSession. The default is **Offline template baseline** with CP-SAT; this uses narrowly matched fixture reports and the real scheduler/validator, not hosted inference. Users can select hosted single-agent or multi-agent mode and either CP-SAT or the heuristic. Selecting or browsing never constructs a hosted client. Hosted generation is disabled if provider/model/key preflight fails.

An explicit Generate plan action starts one bounded request. The UI displays:

- Recorded run status and independent validation, including violations when supplied.
- Actual action catalogue IDs, assignments, targets, generator, route, departure, work start/end and duration.
- Planned travel/work timeline and explicit unmet needs.
- Resolved facts with evidence IDs/status/reason and unresolved observations.
- Actual coordinator messages, with deterministic template/scheduler exchanges distinguished from hosted agents.
- Run ID, scenario/state version, transport, start time, metadata, reported token usage, request details and warnings.

Planner availability/downtime predictions remain in a separately labelled expander. They are not simulator measurements. No financial savings, service-restoration outcome or single-/multi-agent superiority is claimed.

## Duplicate requests and stale state

The service records an attempted request key before client construction. The key binds input hash/path, mode, scheduler, model/provider/endpoint fingerprint and an explicit attempt generation. Busy or already-attempted requests are no-ops. Every retry requires Start a new attempt or a deliberately different request configuration; no network/schema failure silently starts another UI run. The existing adapter's single schema repair remains within the shared global budget.

Start a new attempt retires the current plan, approval and simulation result. Starting any replacement request also retires them before client setup, including when setup fails. Scenario/content changes clear that scenario's request ledger, results and approval through the existing session boundary. Navigation preserves the current run and mode/scheduler preferences; widgets do not automatically request work on return. A single app session is not durable idempotency across server restarts or reconnects.

CoreSession now reserves monotonically increasing state versions for Prepare attempts, including failed attempts and UI-cleared plans, and advances beyond versions introduced by an evidence-review loop. A new scenario session starts again at version 1; content-bound approval still guards the exact scenario/plan/state. This is static planning, not continuation of already-started work or event execution.

## Failures, usage and files

The adapter is created only for an explicitly requested hosted run and closed in finally. Setup/workflow errors show a safe phase/error type, never raw SDK exception messages, URLs, headers or credentials. Recorded hosted usage survives an escalated run or later trace failure; incomplete provider usage is not treated as a zero-cost request.

Existing core records are saved under ignored `results/local_runs/<run_id>.json`. Metadata-only UI attempts, including blocked/setup failures, go under `results/local_runs/ui_attempts/` with private file permissions and atomic replacement. The UI warns if attempt metadata cannot be saved and never automatically retries. A core trace write failure stops the request without an active plan, preserving recorded usage in attempt metadata. These records are local synthetic/redacted development artifacts, not an authentication or audit-signature system.

## Run and verify

Stop/restart any existing Streamlit server after applying this update so existing sessions load the new state fields.

```sh
source .venv/bin/activate
python -m pytest -q
python -m streamlit run project/main.py
```

Select Planning → Offline template baseline → CP-SAT optimizer → Generate plan. For DEMO-005, expect awaiting operator approval, independently valid schedule, one G1 deployment at S02, travel minute 0–15, work minute 15–30 and zero model calls. Approval and simulation remain disabled for Push 4. Returning from Incident/Settings must preserve the same run; Generate stays disabled until an explicit new attempt.

For hosted testing, configure the exact model ID and relevant provider key locally in `.env`, restart, then explicitly select a hosted mode and generate. That action sends visible synthetic inputs to the configured provider and may incur charges. Whole-run limits remain 12 calls, 24,000 input and 4,800 output tokens, 180 seconds and at most five seconds per scheduler attempt. Conservative input reservations can exhaust early. No model, provider or offline fallback is selected automatically.

## Actual checks

**117 total tests passed**, including **48 UI/service checks**. The 21 new planning tests cover real offline scheduling and persisted records; request deduplication; explicit retries; monotonic versions after failure/clearing/revisions; stale/mutated inputs; configuration/setup/provider/trace failures; private error handling; retained usage; adapter closure; busy guards; actual timeline/fact projection; scenario resets; control-change labelling; and navigation without inference. Hosted tests use injected fake clients and are explicitly marked injected_test_client; they are not live model evaluations.

Browser verification generated the real offline DEMO-005 schedule and displayed independent validation, action count 1, model calls 0, disabled Generate, the actual action row and a planned 0–15 travel / 15–30 work timeline. A verification screenshot was captured. Temporary browser viewport overrides were reset. No paid API request or independent simulation was performed. Local configuration inspection showed an OpenAI credential present but the exact runtime model ID unset; no secret value was printed or copied.

## Remaining work

Push 4: record operator approval/rejection and wire the simulator callback after Zahra's merge. Push 5: independent measured outcomes and run history. Authentication, dynamic event execution, held-out evaluation and clean-install demonstration remain later work. Do not merge an incomplete dashboard PR solely because Push 3 passes its checks; keep pushing this branch through the agreed milestones.

# Dashboard static simulation integration

## Scope and dependency

This milestone connects the existing operator review workflow to Zahra's real
independent simulator. The loader, evaluator and engine remain Zahra's code.
They currently live on `feature/data-simulator` at `13b00ea`; starter-data PR #4
alone does not install them. The dashboard remains usable if those modules are
absent, and simulation stays disabled. No synthetic callback substitutes for a
missing backend.

The adapter is `project.ui.backend.connect_static_backend`. Application rendering
calls it after scenario selection, so each newly created CoreSession receives its
own callback. Rendering imports modules but never loads truth or runs simulation.
The callback revalidates the selected processed input, loads isolated evaluator
truth only after explicit approval, and passes the current verified state and
approval into the engine. Fixture-only selections do not attach the backend.

Results include documented metric units, service availability intervals, action
outcomes, audit records, exports and read-only history. The adapter records a
truth hash for reproducibility without returning the truth itself.

## Static milestone boundaries

- Static initial episodes only; current_time_min must be zero.
- Episodes containing future events stop with an `unsupported` audit status;
  they publish no partial-horizon measurements and never automatically retry.
- The current simulator misreports the final service count when an event occurs
  exactly at the horizon. Until Zahra fixes this, the adapter refuses plans whose
  work completion or generator expiry falls exactly at that horizon.
- Continuation after resource loss, accumulated metrics across replanning,
  event-driven approval and independently audited evaluation cases remain pending.
- No inference calls or real equipment dispatch are performed by this adapter.

## Reproduce the static demo

With the simulator dependency present, from the repository root:

```bash
source .venv/bin/activate
python scripts/check_data.py
python -m pytest tests/ui/test_static_integration.py -q
python -m streamlit run project/main.py
```

Choose DEMO-005, enter an operator label, open Planning, select Template mode and
CP-SAT, generate and inspect the plan, approve it, then click Simulate approved
plan. Open Results. Expected: S02/S04 service IDs V02/V04 are available on
[30,150); first restoration at minute 30; weighted availability 720 service-minutes;
weighted downtime 5760 weighted service-minutes. Re-rendering must not simulate
again. Changing the scenario removes the old approval and result.

The new eight tests cover missing backend behavior, passive truth isolation,
real approval-to-result execution/history, duplicate execution, approval refusal,
scenario reset/reconnection, unfinished dynamic cases, the horizon safeguard and
a full Streamlit button flow. Backend-dependent tests skip explicitly when the
simulator modules are absent. Template mode makes no model requests; hosted model
quality and live OpenAI transport are separate checks.

## Coordination

Keep edits to project/data and project/simulation with Zahra. Merge the current
main (including PR #4 checksum fixes) into her backend branch before reviewing
and merging it; retain main's corrected manifest and preparation/check scripts
when resolving the older starter-pack additions. Re-run data checks and tests.
When backend continuation and boundary fixes land, replace the adapter's temporary
restrictions with tests for the corrected semantics, rather than removing guards
without validation.

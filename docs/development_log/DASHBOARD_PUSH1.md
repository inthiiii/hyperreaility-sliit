# Dashboard Push 1 — foundation

Implemented 23 November 2026 against merged core `8c4f807` on `feature/dashboard`.

## Available behavior

- Dark Streamlit layout with Overview, Incident, Planning, Results and Settings navigation.
- Scenario selector defaults to DEMO-005 when present. Overview counts come from the selected validated input, not invented restoration results.
- Only `data/processed/agent_inputs/demo` and `development` are listed. If neither contains valid inputs, the six bundled `tests/core/fixtures` files are explicitly labelled development fixtures.
- Strict ScenarioInput validation, 2 MB input limit, duplicate-ID handling and a 100-file scan limit. Linked roots and file links escaping the approved folder are rejected. Raw, hidden-truth and candidate-evaluation folders are not scanned. Rejected file contents are not echoed into UI errors.
- Per-browser-session CoreSession, selection hash/revision and operator label. A different scenario, edited file or removed selection clears previous plans, approvals and results. Navigation and operator-label edits preserve the selected session.
- Credential-safe provider/model readiness display using the existing preflight. No SDK client or API request is created by browsing, rendering, selecting a scenario or switching pages.
- Planning, approval and simulation buttons remain disabled; later milestones connect their actual behavior. No placeholder restoration scores are shown.

## Run

From the repository root, using the existing environment:

```sh
source .venv/bin/activate
python -m streamlit run project/main.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501. No new dependencies are needed. The theme uses system fonts and local CSS; no remote font/image asset is requested. Credentials stay in the local backend environment. Restart the app after changing environment configuration; the indicator confirms presence only, not live model availability.

## Verification

```sh
python -m pytest tests/ui -q
python -m pytest -q
```

Recorded results: **14 UI checks passed; 83 tests passed overall** using the existing Python 3.11 environment with Streamlit 1.67.0. Streamlit AppTest exercised navigation, scenario changes, updated/removed files, empty catalogs, secret-safe configuration, disabled actions, session isolation and zero-inference browsing. Data-boundary tests covered hidden-truth rejection, candidate-evaluation exclusion, symlink escapes, duplicates, malformed JSON and oversized inputs. Test catalogs are temporary, so publishing Zahra's real processed inputs will not invalidate fixture-only test assumptions.

The actual application was also opened in the in-app browser. Overview and Settings rendered, desktop layout was inspected at a temporary 1280×900 viewport, and the narrow layout was inspected with the sidebar collapsed. Temporary viewport overrides were reset. No live model or independent simulation was tested.

## Next pushes

| Push | Scope |
| --- | --- |
| 2 | Network diagram, reports, visible observations and resource detail views |
| 3 | Explicit planning request, fresh Coordinator, actual findings/schedule/validation |
| 4 | Recorded approval/rejection, session identity integration and simulator callback |
| 5 | Independent measured outcomes, run history and presentation QA |

Views currently read the shared ScenarioInput directly; Zahra's future allowlisted loader can replace `load_catalog` at the UI boundary. Hidden evaluator state must remain outside the UI and agent contexts. CoreSession is created per user session, never globally cached. Future model calls belong only in explicit button handlers; use a fresh Coordinator and close the adapter after each run. Do not add model calls to rendering or cached functions.

The operator label is not authentication. Browser reload/reconnect can start a new Streamlit session. Persistent operator approval history and authenticated accounts remain later integration work. Fixture coordinates are fictional local positions, not geographic coverage. No submitted proposal, model adapter, simulator or data-preprocessing module was changed.

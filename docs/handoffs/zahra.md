# Zahra handoff: starter data, loader, independent simulator, metrics

Date: 23 November 2026. Author: Zahra Hassan (HyperReAIlity). Work done with Claude Code (model claude-sonnet-5-5) editing and running commands in the local checkout.

## Branches and commits

| Branch | Content | Base |
|---|---|---|
| `feature/starter-data` (PR 1, merge first) | commit `53fa58a`: starter scripts, data, `DATA_PROCESSING.md`, `DAY_1_PLAN.md` | `main` at `8c4f807` |
| `feature/data-simulator` (PR 2) | loader, evaluator loader, simulator, metrics, tests, this handoff | `feature/starter-data` |

PR 2 contains PR 1's commit until PR 1 is merged. After PR 1 merges: `git fetch origin && git merge origin/main` on `feature/data-simulator` (do not force push).

## Changed files

- Starter pack (PR 1): `scripts/` (4 files), `data/` (210 files incl. raw geoBoundaries provenance, attribution, `file_manifest.csv`, `quality_report.json`), `docs/DATA_PROCESSING.md`, `docs/DAY_1_PLAN.md`.
- `project/data/loader.py`, `project/data/evaluator.py`, `project/data/__init__.py`
- `project/simulation/engine.py`, `project/simulation/metrics.py`, `project/simulation/__init__.py`
- `tests/data/test_data_loader.py`; `tests/simulation/{conftest,sim_helpers,test_sim_engine,test_sim_metrics,test_sim_integration}.py`
- `docs/handoffs/zahra.md`

Not copied from the starter ZIP: its `docs/DATA_CONTRACT.md` (the repository already has Ihthisham's authoritative version), `docs/manual_qa.csv` (Kiruthika's QA sheet; add on her request) and the ZIP `README.md`. No shared files (`schemas.py`, `requirements.txt`, `.gitignore`, `README.md`) were edited.

## Setup and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r project/requirements.txt     # or: pydantic==2.14.4 networkx==3.6.1 pytest==9.2.0 ortools==9.15.6755 openai==3.57.0 python-dotenv==1.2.4
python scripts/check_data.py
python -m pytest tests/data tests/simulation -q
```

Programmatic use:

```python
from project.data.loader import load_case              # agent-safe, allowlisted
from project.data.evaluator import EvaluatorLoader      # harness only, never agents
from project.simulation.engine import simulate, session_callback

result = simulate(scenario, approved_plan, approval, EvaluatorLoader().load(scenario.scenario_id), state=verified_state)

session = CoreSession()
session.simulator = session_callback(session, EvaluatorLoader())   # Eyaas: wires the real simulator
```

`state` is optional but should be passed: it binds the approval to the exact verified state hash.

## Completed

1. Starter data inspected and published (PR 1). Inventory confirmed: 25 districts, 3 Western subset, 1 demo, 10 development, 20 evaluation candidates.
2. `load_case(path) -> ScenarioInput`: reads only `<agent_inputs>/<demo|development|candidate_evaluation>/<ID>.json`; rejects `..`, absolute paths outside the root, wrong depth/extension, oversized files; validates with the shared schema.
3. Separate `EvaluatorLoader`/`EvaluatorTruth` for private truth. A test fails if `project/agents`, `project/core` or `project/llm` mention `ground_truth`, `raw/synthetic`, `project.data.evaluator` or `project.simulation`.
4. `simulate(scenario, approved_plan, approval, isolated_truth)`: requires an approving, matching approval (decision, plan ID, state version, plan hash, state hash, optionally verified-state hash); re-checks plan structure independently; runs on a deep copy of truth; ignores planner predictions. Truth drives equipment/power/link/road state, crew windows and generator autonomy.
5. Full dependency path (site and every upstream site: equipment + power, every link, core), recomputed after every event, each service counted once, cycle/disconnected guard (`TopologyError`).
6. Exact integer-minute integration on half-open intervals; no sampling. Same-minute rule and log order documented in `engine.py`.
7. `metrics.py`: weighted downtime = total weighted horizon minutes - weighted available minutes; unweighted availability; critical service downtime (service-minutes); first restoration (null if none; an initially-up service is not a restoration); services available at horizon end; unmet needs. Also baseline (no action) downtime and reduction. Integrated over [0, horizon), clock never reset.
8. Crew-loss future event (minute 60): completed work preserved, unfinished work of the lost crew paused, observation emitted at its time only, `replan_required` set. Unit-tested; **the replan loop itself is pending** (no continuation of a paused plan; a new state version and approval are required).

## Checks and actual outcomes (Windows 11, Python 3.14.7)

- `python scripts/check_data.py`: PASS (run from the ZIP folder and from the repository).
- All 31 processed inputs validate against `project.core.schemas.ScenarioInput`; 201 manifest SHA-256 values match.
- `python -m pytest tests/data tests/simulation -q`: **146 passed** in about 5 s.
- Whole repository `python -m pytest -q`: 214 passed, **1 failed**: `tests/core/test_premerge.py::test_trace_roundtrip_private_and_tamper` asserts POSIX file mode `0o600`, which Windows does not report. Ihthisham's test; not changed. Likely a Windows-only artefact, not verified on macOS/Linux by me.
- Numerical example (DEMO-005, generator G1 to S02, work ends minute 30, autonomy 120): S02 and S04 available on [30,150), weights total 6, weighted available 720, weighted downtime 5760 of 6480, first restoration 30, critical downtime 600, nothing available at horizon end. Link repair alone restores nothing. Link repair plus generator at S01 restores S01, S03 and S05 on [115,235).
- Integration with Ihthisham's merged core (template mode, no model call): the planned DEMO-005 action simulated to the figures above. Smoke run over all 31 cases: 25 reached awaiting_approval and simulated without error; 6 escalated (unresolved facts) and were not simulated. These are plumbing checks, not benchmark results.

## Model and tools

Claude Code with claude-sonnet-5-5 wrote the code and tests; Python, pytest, Git. Starter pack was produced earlier with ChatGPT/Codex assistance (see `data/ATTRIBUTION.md`). No inference API, no key, no model call in any of my components. API smoke test: not applicable.

## Assumptions

- Version 0.1 scope: tree backhaul, one generator deployment, no grid-repair action, static road travel times.
- A service at site S needs S and all ancestors powered; generator power applies only to its target site.
- Crew-loss patch applies at the event minute; an action ending exactly then completes.
- A failed or paused action blocks that crew's later actions (replanning needed).
- Weights come from `ScenarioInput.services` (schema checks they match policy).
- `SimulationResult` has no per-service field, so per-service intervals and action outcomes are in `run_metadata` (`service_availability`, `action_outcomes`). I did not alter the shared schema.

## Known issues and limits

- All 31 cases are unreviewed synthetic drafts; the 20 evaluation candidates are not a validated held-out set. Do not report benchmark claims.
- District GeoJSON is display context only (ODbL 1.0, represented year 2017); geometry topology was not validated; fictional x/y never mixed with lon/lat.
- Git on Windows may store `data/processed/context/districts.csv` with LF while `file_manifest.csv` hashes the original CRLF bytes; the manifest test accepts either. A `.gitattributes` for `data/` would remove this ambiguity (shared file; Ihthisham's call).
- I did not see a separate "Data and Simulation Handbook" file, only the work guide; its extra requirements may not be reflected.
- Persisted/idempotent execution across restarts and rolling-horizon replanning remain integration work.

## What others must connect

- Ihthisham: review PR 1 then PR 2; add pinned dependencies if wanted; decide on the Windows file-mode test and `.gitattributes`.
- Eyaas: `session.simulator = session_callback(session, EvaluatorLoader())`; read `metrics`, `trajectory`, `run_metadata['service_availability']`; show `run_metadata['replan_required']`; never import `project.data.evaluator` in dashboard code that agents can reach.
- Kiruthika: `manual_qa.csv` is available in the starter ZIP; QA the scenario text and flag problems rather than editing evaluation files in place.

## Staged files and PR steps

```powershell
git add project/data project/simulation tests/data tests/simulation docs/handoffs/zahra.md
git diff --cached --stat
git commit -m "Add loader, independent simulator and metrics"
git push -u origin feature/data-simulator
```

Open PR 1 (`feature/starter-data` to `main`) first, request Ihthisham's review, merge, then open PR 2 (`feature/data-simulator` to `main`) with these checks and limits.

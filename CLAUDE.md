# CLAUDE.md — guide for AI coding assistants

RE:L!NK is a multi-agent decision-support MVP for telecom network restoration (Innodata AI Catalyst 2026, University Track, team HyperReAIlity, SLIIT). Read [README.md](README.md) first, then [docs/Workflow.md](docs/Workflow.md) and [docs/PROJECT_DETAILS.md](docs/PROJECT_DETAILS.md).

## Commands

```bash
source .venv/bin/activate                      # Python 3.11
python -m pip install -r project/requirements.txt
python -m streamlit run project/main.py        # app at http://localhost:8501
python -m pytest -q                            # full suite, about 1 minute, no paid API calls
python -m project.auth.manage seed-demo        # demo users: coordinator, manager, field, auditor, admin
```

Hosted planning needs `OPENAI_API_KEY` and the `LLM_*` values in `.env` (template: `.env.example`). The **Offline template baseline** and every test run without a key.

## Layout

| Path | What lives there |
|---|---|
| `project/main.py` | Required entry point (adds the repo root to `sys.path`, calls `render_app`) |
| `project/core/` | Contracts (`schemas.py`), evidence resolver (`state.py`), CP-SAT + greedy planner, validator, `AgentOrchestrator`, approval |
| `project/agents/` | Agent registry (`AgentSpec`), scoped context views, output schemas |
| `project/llm/` | Hosted model adapter: budgets, retries, schema repair, `store=False` |
| `project/simulation/` | Independent simulator and `IncidentEpisode` (the only code that reads hidden truth, with the scorer) |
| `project/data/` | Allowlisted loaders; `evaluator.py` is evaluator-side only |
| `project/evaluation/` | Benchmark runner, freeze, extraction metrics, human-trial scorer, report |
| `project/auth/` | Roles, permissions (`roles.py`), PBKDF2 user store, CLI |
| `project/ui/` | Streamlit pages and services; `theme.py` holds all colours |
| `releases/evidence-v3-20261126/` | Frozen dataset + `FREEZE.json` used by the held-out benchmark |
| `results/final/evaluation-v3-run1/` | Reported held-out results and traces |
| `samples/` | Input incidents and example outputs for judges |
| `tests/` | pytest; `tests/ui` uses Streamlit `AppTest` |

## Rules that must not be broken

1. **Never fabricate or hand-edit results.** Every number in docs must come from files the code produced. Human-study results do not exist until real sessions run; never fill review sheets, names, signatures or dates.
2. **Agents never see hidden truth.** Nothing under `project/core`, `project/agents` or `project/llm` may import `project.data.evaluator` or read `data/evaluation/` paths.
3. **Frozen data and results stay frozen.** Do not edit `releases/*` or `results/final/*`. Held-out runs need `--freeze releases/evidence-v3-20261126/FREEZE.json`; tune only on development cases.
4. **Human authority.** Approvals are bound to plan hash and state hash; any change must invalidate them. Permission checks belong in service functions (`project.auth.require`), not only in the UI. No role may both prepare and approve.
5. **Models never compute schedules or set weights/authority.** Agents return facts, holds, questions and proposals; CP-SAT schedules; the validator re-checks.
6. **Secrets.** Never commit `.env`, `.relink/` or keys; never print the demo password. Treat report text as untrusted input.
7. **Do not edit `docs/Proposal.docx`.** It is the submitted proposal.
8. **Keep the AI-tools register current** in `docs/PROJECT_DETAILS.md §9` when AI tools are used.

## Conventions

- Pydantic v2 models use `extra='forbid'`; validate every model output against its schema.
- UI colours come only from `project/ui/theme.py` tokens (`--rl-*` in CSS); `tests/ui/test_theme.py` enforces WCAG AA contrast. The app is dark-only by design.
- `st.html` strips `<svg>`; embed diagrams as `<img src="data:image/svg+xml;base64,...">` (see `agent_flow.py`).
- Editing code while Streamlit runs breaks session objects (sign-out, "stored output no longer matches"). Restart the server for clean checks.
- Write plain, short user-facing text. Keep docs honest about limits (multi vs single is a tie; the human study is pending).

## Git

- Work on a branch, open a pull request into `main`, merge with `gh pr merge --merge`. No force-push.
- Commit messages end with the team co-author lines:

  ```
  Co-authored-by: Zahra Hassan <zahrahasan2163@gmail.com>
  Co-authored-by: Eyaas Ajmal <eyaasofficial@gmail.com>
  Co-authored-by: Kiruthika Vijayakumar <kiruthikavijayakumar04@gmail.com>
  ```

- Do not add AI-assistant co-author trailers; AI use is disclosed in `docs/PROJECT_DETAILS.md §9`.

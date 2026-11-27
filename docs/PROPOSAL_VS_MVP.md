# Proposal vs MVP — what we added and what changed

Innodata AI Catalyst 2026 · University Track · Team HyperReAIlity (SLIIT) · 27 November 2026

This file compares the submitted MVP with [Proposal.docx](Proposal.docx) (submitted 20 November 2026, not edited since). It lists, separately:

1. **Additions:** capabilities in the MVP that the proposal did not plan.
2. **Changes:** places where the MVP does something different from the plan, or less.
3. **Delivered as planned:** for completeness.

Nothing below changes the reported results; all results come from the submitted code ([results/final/evaluation-v3-run1](../results/final/evaluation-v3-run1/README.md)).

## 1. Additions (not in the proposal)

| # | Addition | Why we added it | Where |
|---|---|---|---|
| A1 | **Sign-in with five roles** (NOC Coordinator, Restoration Manager, Field Supervisor, Auditor, Administrator) and separation of duties enforced in the service layer | The proposal had one "human approver". Real operations split preparing, approving and auditing; the approver can never be the person who generated the plan. | `project/auth`, `project/ui/auth_view.py` |
| A2 | **Partial plans with operator questions** instead of escalating the whole run when a fact is unknown | Early runs escalated 50–60 % of the time. Now the plan covers what is certain and the agents ask targeted questions. | `project/core/orchestrator.py` |
| A3 | **Operator inbox with inline answers and automatic replanning**: an answer is recorded as signed evidence and a new plan is generated at once | Closes the human-in-the-loop cycle in one place. | `project/ui/inbox_answer.py` |
| A4 | **Priority proposals**: the Service Priority Assessor can propose (never apply) a priority change; the manager accepts or rejects it | Keeps weights human-controlled while letting the agent surface context from the reports. | `project/ui/priority_service.py` |
| A5 | **Distractors and prompt-injection measurement**: reports include complaints, rumours and instruction attempts; the evaluator counts claims citing distractors and injections followed | The proposal treated report text as untrusted; we added a measured test of it (0 of 130 injection runs followed). | `scripts/build_evidence_v3.py`, `project/evaluation/extraction.py` |
| A6 | **Realistic evidence v3**: reports written as NMS alarms, field WhatsApp messages, road bulletins and duty-manager notes, with site aliases and a site directory | Fixed one-line reports could be parsed by a regex, so agents could not add value. | `releases/evidence-v3-20261126` |
| A7 | **Real Western Province geography**: sites placed at public town coordinates (fictional sites and faults), district boundaries from geoBoundaries (ODbL) | Readable map for operators and judges. | `data/processed/context`, `data/ATTRIBUTION.md` |
| A8 | **Live agent-workflow diagram** during planning and a free **replay** of the recorded run | Makes the multi-agent exchange visible (competition rule 02). | `project/ui/agent_flow.py` |
| A9 | **Map as a four-chapter story**: reported damage, what the agents established, the plan with crew routes, restoration replay with live KPIs | Explains the incident and the result without reading tables. | `project/ui/map_page.py`, `map_view.py` |
| A10 | **Crew Gantt timeline**, agent conversation view and evidence view | Explainability of each plan. | `project/ui/planning.py`, `agent_view.py` |
| A11 | **Field work page**: crew job lists and field updates that cancel approval and force replanning | The proposal described event-driven replanning; this adds the field role's entry point. | `project/ui/map_page.py` (`render_field_page`) |
| A12 | **What-if sandbox**: remove a crew or close a road, see if the current plan still works, replan with CP-SAT and compare in the simulator. No model calls, no change to the real plan | Lets a manager test plan fragility before events happen. | `project/ui/whatif.py`, `whatif_page.py` |
| A13 | **Incident upload (JSON)** checked by the same loader and state builder as the dataset (size, schema, duplicate ID, no evaluator keys) | Shows the system works on new incidents, not only our cases. | `project/ui/upload_service.py` |
| A14 | **Role-based notifications**: red badges and a "For you now" list per role | Handover between roles without phone calls. | `project/ui/notifications.py` |
| A15 | **No-AI comparison on the Results page** (CP-SAT without agents on the same incident, same simulator) | Shows the value of the agents on every incident, not only in the benchmark. | `project/ui/baseline_compare.py` |
| A16 | **One-page plan summary PDF** (jobs, agent reasons, approval, measured result, comparison) from Results and History | Shareable record for handovers and audit. | `project/ui/plan_export.py` |
| A17 | **Benchmark page and read-only History** with CSV/JSON exports | Evidence and audit trail inside the product. | `project/ui/benchmark_page.py`, `history.py` |
| A18 | **Configuration freeze tool** that hashes the code commit, model, prompts and data before the held-out run and stops on drift | Makes "no tuning on held-out cases" verifiable. | `project/evaluation/freeze.py`, `releases/evidence-v3-20261126/FREEZE.json` |
| A19 | **Human-baseline scorer** that turns a manual crew order into a timed plan and scores it with the same validator and simulator | The proposal planned the study; this is the tool that makes the comparison fair. | `project/evaluation/human_trial.py` |
| A20 | **Multi-agent variant controls**: `no_feedback` ablation plus v13 `matched_single` / `matched_multi` controls, and a priority heuristic | More controls than the proposal's single ablation pair. | `project/evaluation/runner.py` |
| A21 | **Responsive dark interface** with the RE:L!NK brand and accessibility contrast tests | Usability for long incident shifts. | `project/ui/styles.css`, `theme.py`, `tests/ui/test_theme.py` |

## 2. Changes and shortfalls against the proposal

| # | Proposal said | MVP does | Reason / status |
|---|---|---|---|
| C1 | Multi-agent ≥ 10 % median downtime reduction vs single agent | **Not met.** Multi vs single: 2 better, 15 ties, 2 worse (95 % CI −596 to 57). | Reported honestly; no superiority claimed. Both agent variants beat CP-SAT without AI (multi: 13 better, 0 worse). |
| C2 | Evidence F1 ≥ 0.90 | Multi 0.88 → 0.88 after review; single 0.96 → 0.95; no-Reviewer 0.94 | Target met by single and no-Reviewer, not by full multi. |
| C3 | Plan Reviewer adds value (ablation) | Multi without the Reviewer was the most reliable (60/60) and cheapest; the Reviewer did not improve outcomes on this set | Reported in the benchmark. |
| C4 | Exploratory human study on 26 Nov (4 people × 6 cases) | **Not run yet.** Protocol, answer sheets and scorer are ready ([human_baseline/README.md](human_baseline/README.md)). | No human results are claimed. See [HUMAN_REVIEW_DISCLOSURE.md](HUMAN_REVIEW_DISCLOSURE.md). |
| C5 | Kiruthika (who did not build the planner) audits held-out facts | The held-out set was **AI-generated and AI-reviewed** by script and coding assistant, with mechanical checks; no independent human review | Disclosed in [development_log/PRIORITY_5_AI_COMPLETION.md](development_log/PRIORITY_5_AI_COMPLETION.md). |
| C6 | MVP models 15–20 sites | Development and held-out cases have 15–20 sites; the **demo incident has 5 sites** for a readable live demo | Benchmark uses the planned scale. |
| C7 | Stress tests at 20, 50 and 100 sites | **Not run.** Largest tested case is 20 sites. | CP-SAT is capped at 5 s with a greedy fallback; larger scales are future work. |
| C8 | Field Resource Planner proposes feasible actions | It returns evidence-linked **holds** (`defer_action`) and operator questions; the schedule always comes from CP-SAT | Keeps the model out of arithmetic (LLM-Modulo design). |
| C9 | SQLite plus JSON/CSV storage | JSON and CSV records only (checksummed run, decision and simulation files) | Simpler for a two-week build; no database. |
| C10 | OpenStreetMap roads/facilities; OpenCellID optional | geoBoundaries district boundaries (OSM-derived, ODbL) and public town coordinates; road network is synthetic; OpenCellID not used | No real tower inventory is needed or used. |
| C11 | Report outcomes by geographic group | Critical-service downtime is reported; per-district outcome breakdown is not | Future work. |
| C12 | "Hosted model chosen during development" | OpenAI `gpt-6-luna`, reasoning `none`, Responses API with strict JSON Schema, frozen before the held-out run | Selection recorded in `FREEZE.json`. |
| C13 | Operator approval authorizes simulation | Same, plus in the benchmark an **automated benchmark operator** approves plans so 360 runs can be scored | Labelled in every simulation record (`approval_mode`). |

## 3. Delivered as planned

Four specialist agents with scoped contexts and typed messages through a deterministic coordinator; evidence resolver with authority rules; CP-SAT scheduler (≤ 5 s); independent validator; hash-bound human approval that expires on any change; independent simulator with power, backhaul and generator-autonomy semantics; mid-incident resource-loss replanning; whole-run budgets (12 calls, 24k input / 4.8k output tokens, 180 s) with bounded retries; tool-assisted single-agent baseline under the same caps; heuristic and CP-SAT references; 10 development and 20 frozen held-out cases × 3 repeats; paired medians with bootstrap intervals; JSON traces with token usage, request IDs and cost; Streamlit dashboard; pytest suite.

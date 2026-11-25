# RE:L!NK — Project Details

**Restore connectivity. Coordinate recovery.**

| Item | Details |
|---|---|
| Competition | Innodata AI Catalyst 2026, University Track |
| Domain | Telecommunications |
| Team | HyperReAIlity, SLIIT |
| Repository | https://github.com/inthiiii/hyperreaility-sliit |
| Document version | 1.0 (agent protocol `relink-agents-v14`, evidence v3, role-based access) |
| Last updated | 25 November 2026 |
| Related | [Proposal.docx](Proposal.docx) · [Workflow.md](Workflow.md) · [PROJECT_PLAN.md](PROJECT_PLAN.md) |

Earlier versions and daily checkpoints are archived in [development_log/](development_log/).

## 1. Problem and users

After a cyclone or flood, telecom operators must decide which sites to restore first with too few crews, generators and open roads, from reports that are incomplete, duplicated, stale or contradictory. A site only carries traffic when its **equipment works, it has power (grid or generator) and its backhaul path to the core is up**, so fixing one prerequisite in isolation can restore nothing. After Cyclone Ditwah (2025), one Sri Lankan operator reported 2,200 of 6,000 sites affected (sources in the proposal).

- **Primary users:** NOC coordinators, restoration managers and field supervisors.
- **Indirect beneficiaries:** subscribers, hospitals, emergency services and businesses.

## 2. What the MVP does (implemented)

| Capability | Where |
|---|---|
| Sign in; five roles with separation of duties enforced in the service layer | `project/auth`, `project/ui/auth_view.py` |
| Load a validated synthetic incident (sites in real Western Province towns, fictional faults) | `project/data/loader.py`, `releases/evidence-v3-20261126` |
| Four AI specialists turn messy reports into evidence-linked facts, holds, questions and priority proposals | `project/core/orchestrator.py`, `project/agents/registry.py` |
| Deterministic evidence resolver, CP-SAT scheduler, independent validator, service forecast | `project/core/` |
| Reviewer challenges routed back to the Investigator; bounded revision (≤ 3 rounds) | `orchestrator.py` |
| Partial plans with operator questions instead of whole-run escalation for unknowns | `orchestrator.py` |
| Hash-bound human approval; any change revokes it | `project/core/coordinator.py`, `project/ui/review_service.py` |
| Independent simulator against hidden truth; crew-loss events pause, then need a fresh plan and approval | `project/simulation/` |
| Dashboard: Overview, Incident, Planning, Results, History, Settings | `project/ui/` |
| Benchmark runner: heuristic, CP-SAT, single agent, multi agent, ablations, legacy controls | `project/evaluation/runner.py` |
| Human-baseline scorer using the same validator and simulator | `project/evaluation/human_trial.py` |

**Out of scope:** real network control, autonomous dispatch, radio coverage prediction, generator refuelling, national scale, production identity (SSO/MFA).

## 3. Multi-agent design

| Agent (AI) | Sees (scoped context) | Produces | Cannot |
|---|---|---|---|
| Network Investigator | Reports, site directory (names, codes, aliases), links, roads, authority rules | Facts with report IDs; ignored reports with a reason (`no_operational_claim`, `instruction_attempt`, `duplicate_or_echo`) | Set authority, invent IDs |
| Field Resource Planner | Crews, generators, roads (resolved), action catalogue, resolved state, Investigator facts | Evidence-linked `defer_action` holds; ≤ 4 operator questions | Change constraints |
| Service Priority Assessor | Services, approved policy, resolved state, reports, ignored-report flags | Trade-off notes; priority **proposals** for the manager | Change weights |
| Plan Reviewer | Raw reports, extracted facts, plan, validation, arithmetic checks, forecast (**not** the Investigator's reasoning) | Approve / revise / escalate; fact challenges; holds | Approve for execution |

**Why multiple agents:** each job needs different information and a different stance (reading noisy text, scheduling constraints, policy, adversarial checking). Scoped contexts keep each prompt small, and an independent reviewer re-checking source text catches errors that self-review tends to repeat. This is a hypothesis, tested against a single agent with the same model, tools, evidence and caps (see §6).

**Software, not agents:** the coordinator (routing, versions, budgets), evidence resolver, CP-SAT scheduler, validator, forecast and simulator.

**Extensibility:** a new agent is one `AgentSpec` (role, task, schema, output cap, view function) in `project/agents/registry.py`.

## 4. Technology choices

| Layer | Choice | Why / alternative considered |
|---|---|---|
| Language | Python 3.11 | Team skills; OR-Tools and NetworkX available |
| Orchestration | Own coordinator (`AgentOrchestrator`) | Explicit budgets, versions and permissions; LangGraph and CrewAI considered but add abstraction we would need to audit |
| LLM | OpenAI `gpt-6-luna`, Responses API, strict JSON Schema, reasoning `none` | Reliable structured output and low latency; provider adapter also supports OpenRouter |
| Graph | NetworkX | Dependency paths and road routing |
| Scheduling | OR-Tools CP-SAT (time-indexed, 5-minute slots, ≤ 5 s) | Precedence + no-overlap; greedy fallback if not solved; MILP was the alternative |
| Contracts | Pydantic v2 | Schema validation everywhere, including model outputs |
| UI | Streamlit 1.67 | Fast operator dashboard; AppTest for UI tests |
| Auth | PBKDF2-SHA256 (240k iterations), local users file | No external identity provider in a 2-week build |
| Tests | pytest (569 tests) | Contracts, scheduler, validator, simulator, agents, UI, auth |

Dependencies are pinned in `project/requirements.txt`.

## 5. Data

- **evidence v3** (`releases/evidence-v3-20261126`): 31 cases (1 demo, 10 development, 20 EVAL2) built deterministically by `scripts/build_evidence_v3.py` from the frozen v2 release.
  - Reports are NMS alarms with site codes, road bulletins, field WhatsApp messages and duty-manager notes.
  - Each case has 2–4 distractors (complaint, irrelevant notice, rumour, prompt injection in about half).
  - Labels and truth are evaluator-only.
- **Geography:** sites are placed at public town-centre coordinates in Colombo, Gampaha and Kalutara for readability; **sites, codes and faults are fictional**. District boundaries come from geoBoundaries (ODbL), see `data/ATTRIBUTION.md`.
- **Limits:** synthetic phrase banks; not independently human-reviewed yet; no operator data.

## 6. Benchmark and evaluation

- **Systems:** priority heuristic (greedy), CP-SAT on agent-free state, single agent (one context), multi agent, multi without Reviewer, multi without feedback, plus v13 `matched_*` controls and human participants.
- **Cases:** 10 development cases (tuning allowed) and 20 EVAL2 cases (frozen before running; no tuning). 3 repeats per hosted variant.
- **Fairness:** same model, settings, tools, evidence, caps (12 calls / 24k in / 4.8k out / 180 s) and simulator.
- **Metrics:**
  - weighted service downtime (primary) and critical-service downtime;
  - plan validity and escalations;
  - fact precision, recall and F1 (initial and after review);
  - claims citing distractors, and injection followed or flagged;
  - operator questions and fact challenges;
  - calls, tokens, latency and USD cost at dated prices.
- **Human baseline:** up to 4 participants × 6 cases, ≤ 10 min each, manual schedule via the Auditor view, scored by the same tools ([human_baseline/README.md](human_baseline/README.md)).
- **Held-out results (25 Nov, frozen EVAL2):** [report](../results/final/evaluation-v3-run1/README.md).
  - Agents beat CP-SAT without AI: multi better on 13 of 20 cases and never worse (95 % CI −4,044 to −981 weighted minutes).
  - Multi vs single: not significant (2 better, 15 ties, 2 worse; target not met).
  - Multi without the Reviewer was the most reliable (60/60) and cheapest configuration.
  - 0 of 130 injection runs followed.
- **Development evidence (25 Nov):** [tuning passes](../results/development/v14-dev-tuning-20261125/README.md). Agents lower downtime against CP-SAT without AI on 8 of 11 cases. Single and multi tie on every case both completed. Before tuning, the single agent exhausted its budget on 4 of 11 cases versus 0 for multi. Injection reports were flagged and never followed. The EVAL2 configuration is frozen ([FREEZE.json](../releases/evidence-v3-20261126/FREEZE.json)). **No multi-agent downtime advantage is claimed.**

## 7. Safety, security and reliability

- Report text is untrusted. Prompts say so, and authority, weights and permissions are never model-controlled. Injection attempts are measured.
- Secrets live only in `.env` (git-ignored). Password hashes live in `.relink/` (git-ignored). Only synthetic data is sent to the API, with `store=False`.
- Budgets, bounded retries, ≤ 5 s solver with fallback, and schema validation of every model output. Invalid facts are dropped individually and logged.
- Human approval is hash-bound to the plan and state; roles separate preparing from approving; decisions record the username and role.
- Traces record every message, tool output, usage record, retry and decision.

## 8. Team

| Member | Area |
|---|---|
| Ihthisham Irshad (lead) | Architecture, agents, integration |
| Zahra Hassan | Data, loader, simulator, metrics |
| Eyaas Ajmal | Interface, workflow, approval, access control |
| Kiruthika Vijayakumar | QA, evaluation protocol, documentation |

## 9. AI tools, services and third-party components (disclosure)

| Item | Use |
|---|---|
| **ChatGPT / Codex (OpenAI)** | Coding assistant for the proposal, core, simulator integration, dashboard and tests up to 25 Nov (see `development_log/`). Session model IDs were not recorded. |
| **Claude Code (Anthropic, model Claude Opus 5.5)** | Coding assistant on 25 Nov in Ihthisham's session: gap review and plan, evidence v3 generator, v14 orchestrator and agent registry, adapter retries, sign-in and roles, human-trial scorer, map / Gantt / conversation / inbox / field pages, development tuning, configuration freeze, documentation. |
| **OpenAI API, `gpt-6-luna`** | Runtime model for all agent roles and the single-agent baseline (Responses API, reasoning `none`). |
| Claude-labelled proposal draft | Comparative drafting reference during the proposal stage only. |
| Libraries | pydantic, ortools, networkx, openai, streamlit, pandas, numpy, python-dotenv, pytest (versions in `project/requirements.txt`; open-source licences). |
| Data | geoBoundaries Sri Lanka ADM2 (ODbL, OpenStreetMap-derived); approximate public town coordinates; all incidents synthetic. |

Runtime model inference is separate from coding assistance. All reported results come from the submitted code; failures are kept.

## 10. Known limitations

- Synthetic data and simplified physics; not field-validated.
- The human study is not run yet; the held-out set is synthetic and not reviewed by a person.
- The model is still the same model in every role, so the comparison tests workflow design, not model diversity.
- Demo-grade authentication; local JSON records, not a database.

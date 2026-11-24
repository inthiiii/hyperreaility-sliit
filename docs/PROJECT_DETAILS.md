# RE:L!NK — Project Details

**Restore connectivity. Coordinate recovery.**

| Item | Details |
| --- | --- |
| Competition | Innodata AI Catalyst 2026 — University Track |
| Domain | Telecommunications |
| Team | HyperReAIlity |
| University | Sri Lanka Institute of Information Technology (SLIIT) |
| Repository | https://github.com/inthiiii/hyperreaility-sliit |
| Document version | 0.9 — selected Luna and real hosted execution checkpoint |
| Last updated | 24 November 2026 |
| Proposal | [Proposal.docx](Proposal.docx) |
| Process description | [Workflow.md](Workflow.md) |

## 1. Current implementation status

The completion branch now contains Zahra's preprocessing assets, typed allowlisted
loader, separate evaluator, independent physical simulation, deterministic metrics
and approval-gated incident continuation. Static scheduling, recorded review,
source/state binding, event-time pauses, safe visible updates and fresh approval
before resume are connected to the dashboard. Full-horizon measurements remain
null until a paused incident completes. The data release is checksummed and
frozen as a candidate snapshot; independent human held-out review remains pending.
See [Zahra acceptance](ZAHRA_ACCEPTANCE.md) and [handoff](handoffs/zahra.md) for
actual checks, run commands and scope limits. See [Luna validation](LUNA_LIVE_VALIDATION.md) for real hosted development observations. Commercial validation, production authentication and real network control remain outside the verified scope.

The selected runtime model is OpenAI `gpt-6-luna`, with explicit reasoning effort `none` and the Responses API. Real hosted demo execution is verified. Development comparisons freeze the model, settings, protocol and budgets; other models may be evaluated on development cases before independent held-out evaluation. The installed SDK remains recorded in project/requirements.txt. Local LLM execution is outside the current implementation plan.

## 2. Problem, users and objectives

Restoring a telecom site requires working equipment, adequate power and an available backhaul path. Limited crews, generators, access routes and contradictory reports make repair order and resource allocation difficult.

Primary users are network operations managers, incident coordinators and maintenance planners. Subscribers, enterprises, hospitals and emergency services are indirect beneficiaries.

RE:L!NK aims to:

- Extract evidence-linked facts and expose missing or contradictory information.
- Produce feasible repair and backup-power schedules.
- Apply human-approved service priorities and show unmet needs.
- Revise recommendations when incidents or resources change.
- Preserve human approval, agent traces and explanations.
- Measure whether specialist collaboration improves on comparable single-agent tooling.

The proposed business value is more productive field-resource use, continuity of important services and auditable decisions. Commercial validation follows practitioner interviews, authorized historical replay and a read-only pilot. Financial savings are not reported as achieved results.

## 3. MVP scope and features

The core demonstration models one fictional operator with 15–20 sites, two repair crews and limited generators. Supported actions are equipment repair, link repair and generator deployment. A fixed 12-hour simulation horizon supports consistent comparisons.

Planned features include scenario loading, report interpretation, dependency investigation, resource allocation, constrained scheduling, independent validation, approval, simulation and event-driven replanning. The interface will display actions, assigned resources, prerequisites, timing, evidence IDs, validation findings and unresolved needs.

Live network control, autonomous crew dispatch, detailed radio propagation, national deployment and generator fuel replenishment are excluded. A simulated restored service does not establish actual radio coverage.

## 4. Multi-agent architecture

| Component | Responsibility and output |
| --- | --- |
| Network Investigator | Interpret reports and graph dependencies; produce evidence-linked faults, prerequisites and clarification questions. |
| Field Resource Planner | Check skills, availability, access and backup power; produce resource constraints and feasible actions. |
| Service Priority Assessor | Apply approved service weights; explain service trade-offs without inventing policy. |
| Plan Reviewer | Challenge evidence and candidate plans; request revisions or escalation. |
| Deterministic coordinator | Route messages, enforce budgets, version shared state and manage approvals. This is software, not a fifth AI agent. |
| Graph tools, scheduler and validator | Calculate connectivity, schedule constrained actions and independently check encoded feasibility. |

Agents use separate role prompts and contexts. The primary benchmark uses the same hosted model across all roles and the single-agent baseline. Per-role model changes, if explored, will be reported separately.

Typed messages will carry sender, recipient, incident ID, state version, finding, evidence IDs and requested action. Shared state will store observations, verified facts, open conflicts, topology, resources, priorities, schedules, validation and approvals. The detailed sequence is in [Workflow.md](Workflow.md).

## 5. Planned technologies and dependencies

| Layer | Planned choice |
| --- | --- |
| Language and orchestration | Python 3.11+; explicit coordination loop and provider adapter |
| Initial LLM integration | OpenAI API through its Python SDK |
| Network analysis | NetworkX |
| Scheduling | Google OR-Tools CP-SAT |
| Schema validation | Pydantic |
| State and exchange | SQLite, JSON/CSV and JSONL traces |
| Operator interface | Streamlit |
| Verification | pytest, scenario fixtures and independent feasibility checks |

The installed environment is recorded in `project/requirements.txt`; the current checks use Python 3.11 and Streamlit 1.67.0. The README contains the dashboard launch command. Final clean-install and full-system dependency verification remain due before submission. Credentials must remain backend environment variables and must never enter Git.

## 6. Data, licences and simulator assumptions

The required dataset will be reproducible synthetic networks, resources, service associations and incident reports. Public OpenStreetMap data may supply geographic context with ODbL attribution. OpenCellID is optional, subject to access and licence checks, and is not an operator's physical-site inventory. No authorized operator topology or alarm history is currently available.

Initial synthetic parameters are repair durations of 30–120 minutes, travel of 5–60 minutes and generator autonomy of 2–6 hours. Publish exact parameters, approved service weights and sensitivity variations with the fixtures. These values are simulation assumptions.

Each adopted dataset needs a manifest recording provenance, licence, access date, transformations, seed and whether fields are public, derived or synthetic. Service objects must prevent overlapping-site double counts. Kiruthika will audit held-out facts and constraints against simulator state without implementing the planner; hidden evaluation labels remain unavailable to agents.

## 7. Benchmarking and acceptance plan

Compare a priority heuristic, conventional CP-SAT, tool-assisted single agent, RE:L!NK and human participants. Test reviewer removal and disabled inter-agent feedback separately under matched budgets.

- Use 10 development cases and 20 held-out cases: two held-out cases in each of the ten categories listed in `Workflow.md`.
- Run each AI configuration three times per scenario. Select models using development cases only.
- Match provider, exact model/version, supported generation/reasoning settings, tools, evidence and context limits within each single-/multi-agent comparison.
- Cap an automated run at 12 model calls, 24,000 input tokens, 4,800 output tokens and 180 seconds, including retries and reported reasoning usage where applicable. Cap each scheduler attempt at five seconds. Stop at the first budget cap.
- Record actual usage, API charges, failures and rate limits. Interleave configurations and record seeds where supported. Never switch models silently.
- Target four consenting human participants on six shared small cases, with a manual schedule-entry form, no AI or automatic optimization, up to ten minutes per case, counterbalanced order and disclosed expertise.

Metrics include weighted service downtime, raw service-hours, critical-service interruption, feasibility, evidence precision/recall/F1, planning time, API cost, replanning, reassignments and geographic outcomes. Use each scenario's median across three runs before calculating paired differences; bootstrap scenarios rather than individual repeats. Report valid plans, correct escalations, invalid outputs and timeouts separately.

Proposed acceptance targets are at least 10% median paired downtime reduction versus the single agent on positive-baseline cases, no higher run-failure rate, zero encoded violations in accepted plans, evidence F1 ≥0.90 and automated runs within 180 seconds. Report zero-baseline cases, all-case absolute differences, unmet targets and negative findings. No benchmark results are available in this initial document.

## 8. Safety, security and reliability

Only synthetic or explicitly authorized, appropriately redacted data may be sent to external APIs. Exclude confidential organizer materials from external requests and follow their authorized-use and deletion requirements. Review provider data-handling terms before using approved operator data.

Treat reports as untrusted data, restrict tool permissions and keep API keys out of source code and logs. Human approval authorizes simulation only. Material changes expire approval. Unresolved critical facts, failed validation, exhausted budgets or unavailable APIs trigger controlled revision or escalation.

The coordinator will retain at most three revision rounds and one schema-repair retry per model response. Transient API retries and backoff must fit within the same global call/token/time budgets. The scheduler must never silently relax constraints.

## 9. Team and delivery

| Member | Proposed work allocation |
| --- | --- |
| Ihthisham Irshad — Team Leader | Architecture, scheduling, agent coordination and integration |
| Zahra Hassan | Data preprocessing, loader, independent simulator and metrics |
| Eyaas Ajmal | Interface, workflow and approval |
| Kiruthika Vijayakumar | Manual QA, defect reports and documentation support |

Development starts on 20 November 2026. Target internal MVP and complete project plan upload is **28 November, 6:00 PM Sri Lanka time**; official Phase 1 deadline is **29 November, 11:59 PM**. Finalists also implement the features provided on 7 December.

Required paths are `project/main.py`, `project/requirements.txt`, `README.md`, `docs/Proposal.docx`, `docs/Workflow.md`, `docs/PROJECT_DETAILS.md` and `project-demo.mp4`. Add input/output samples, traces and evaluation evidence. The video must show actual execution and meet the specified MP4/H.264/AAC, 5–10 minute, minimum 720p and maximum 100 MB requirements.

## 10. AI-tool and third-party disclosure register

| Tool, service or material | Use and current status |
| --- | --- |
| ChatGPT / Codex — OpenAI | Used for proposal/documentation, core code and tests, and dashboard Pushes 1–5 implementation, verification and handoffs. Exact session model identifiers were not recorded. This coding assistance is separate from runtime model inference; no live API inference was performed for these checkpoints. |
| OpenAI API | `gpt-6-luna`, reasoning `none`, Responses API with exact server input counting; live demo and development comparison on 24 November 2026. SDK 3.57.0. All four roles and the single-agent baseline use the same selected model/settings. Usage and actual failure outcomes are recorded; charges remain unmeasured. |
| Claude-labelled proposal draft supplied by the team | Used as comparative drafting/reference material during proposal review. Originating model/version is not independently verified; team members must record any direct Claude use and its purpose. This is not evidence of a Claude runtime integration. |
| Other hosted models | Planned development comparison; add actual provider/model/version, dates, settings and purpose when tested. |
| Python libraries and public datasets | Planned components listed above; record adopted versions, licences, attribution and modifications when used. |

Every team member must add any other AI model, service, coding assistant, reused code or pre-existing component actually used. For each integrated model record provider, exact ID/version, supported settings, SDK, role, evaluation dates and usage/cost evidence. Record reused code provenance and modifications. No pre-existing RE:L!NK application implementation is established by this initial record.

## 11. References and update checklist

The research context and full bibliography are in [Proposal.docx](Proposal.docx). Technical references:

- [OpenAI API reference](https://developers.openai.com/api/reference/overview)
- [OpenAI pricing](https://developers.openai.com/api/docs/pricing)
- [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
- [Google OR-Tools](https://developers.google.com/optimization)
- [OpenStreetMap attribution and licence](https://www.openstreetmap.org/copyright)
- [OpenCellID data-access documentation](https://docs.opencellid.org/docs/downloads/overview)

Before the final MVP submission, replace planned status with verified implementation status, pin dependencies/model configuration, complete the disclosure register, document the actual setup, link execution evidence and reconcile this file with the README, workflow and proposal.


## 24 November continuation disclosure

Zahra's existing code/commits are retained. Ihthisham used ChatGPT/Codex to complete
incident continuation, boundary and loader hardening, data audit/freeze protection,
dashboard integration, tests and handoff. The continuation commits include the
requested Zahra co-author trailer. Python/pytest, Streamlit AppTest and a local
browser were used for verification. No inference API calls or paid model runs were
made. The exact coding-assistant model identifier was not recorded. Earlier
Claude Code tooling/model details in Zahra's handoff are self-reported. Independent
human evaluation review is PENDING and must not be represented as performed by
these coding tools.

## Hosted execution and fairness checkpoint — 24 November

The single-agent baseline now traverses the same investigation, resources, priorities and review stages as the four-role workflow. Both receive the same operational context, deterministic tools and whole-incident caps. Agent requests can conservatively defer evidence-linked actions, version the state, and force a new validated schedule; they cannot change approved weights or mutate evaluator truth.

Benchmark manifests freeze the selected provider/model, endpoint fingerprint, supported generation settings, protocol, runtime and source/input hashes. Paired summaries exclude unsuccessful jobs and model-version mismatches from downtime differences while reporting their counts. Raw extraction F1 is computed before deterministic fixture fill-in and reports label coverage. Charges remain unmeasured. Real Luna smoke checks and development comparisons are now recorded separately from injected-client tests in LUNA_LIVE_VALIDATION.md. See [HOSTED_FAIRNESS.md](HOSTED_FAIRNESS.md).

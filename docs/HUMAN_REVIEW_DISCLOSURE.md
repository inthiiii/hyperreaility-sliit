# Human review and AI assistance — disclosure

Innodata AI Catalyst 2026 · University Track · Team HyperReAIlity (SLIIT) · 27 November 2026

The competition asks for a **documented human comparison or assessment** and for results that come only from the submitted solution. This file states plainly what people did, what AI tools did, and what has **not** been done yet. It complements the AI-tools register in [PROJECT_DETAILS.md §9](PROJECT_DETAILS.md#9-ai-tools-services-and-third-party-components-disclosure).

## 1. Status at a glance

| Item | Status | Evidence |
|---|---|---|
| Human comparison study (participants plan the same incidents by hand) | **Not run yet.** Protocol, answer sheets and scorer are ready. | [human_baseline/README.md](human_baseline/README.md), [guide PDF](human_baseline/RELINK_Human_Comparison_Guide.pdf), `project/evaluation/human_trial.py` |
| Independent human review of the 20 held-out cases | **Not done.** Cases were script-generated and AI-reviewed with mechanical checks. | [development_log/PRIORITY_5_AI_COMPLETION.md](development_log/PRIORITY_5_AI_COMPLETION.md), [evaluation/priority5-20261125](evaluation/priority5-20261125/) |
| Human approval inside the product | **Implemented.** Every plan needs a Restoration Manager's hash-bound approval before simulation. | `project/core/coordinator.py`, `project/ui/review_service.py` |
| Benchmark approvals (360 held-out runs) | **Automated**, labelled `automated_benchmark_operator` in every record. Not human decisions. | `results/final/evaluation-v3-run1/simulations/` |
| Code review | Team members reviewed and merged pull requests on GitHub. AI coding assistants wrote much of the code under the team's direction (see §3). | GitHub pull request history |

**No human result, name, signature or review date has been invented.** Empty review sheets stay empty until a real session takes place.

## 2. Human comparison: how to complete it

1. Recruit up to 4 consenting people who did not build the scheduler or agents. Record expertise only (P1–P4), no names.
2. Follow [human_baseline/README.md](human_baseline/README.md): 6 cases, 10 minutes each, counterbalanced order, Incident page only (signed in as `auditor`).
3. Save one file per participant in `docs/human_baseline/submissions/` from `submission_template.json`.
4. Score with the same validator and simulator as the AI:

   ```bash
   python -m project.evaluation.human_trial --submissions docs/human_baseline/submissions/*.json \
     --data-root releases/evidence-v3-20261126/data --output results/human_baseline/run1
   ```

5. Report the sample size, minutes per case and limits next to the AI results. Update §1 of this file and [PROJECT_DETAILS.md §6](PROJECT_DETAILS.md#6-benchmark-and-evaluation).

## 3. What AI tools did and did not do

| Work | Who |
|---|---|
| Problem choice, domain, research sources, proposal submission, scope decisions, final approval of every change | Team members |
| Proposal drafting | Team, with ChatGPT and a Claude-labelled draft as drafting references |
| Code, tests, data generators, documentation | Largely written by AI coding assistants (ChatGPT/Codex, Claude Code) under team direction, then reviewed and merged by the team |
| Held-out dataset (EVAL2, evidence v3) | Generated deterministically by `scripts/build_evidence_v3.py`; reviewed by an AI assistant with mechanical checks; not independently reviewed by a person |
| Runtime planning in the product | OpenAI `gpt-6-luna` agents, CP-SAT and deterministic software, as described in [Workflow.md](Workflow.md) |
| Benchmark numbers | Produced only by the submitted runner and simulator; not edited by hand |

## 4. Limits this creates

- The held-out cases may share patterns with the generator that also produced the development cases; results are evidence under these synthetic assumptions, not field validation.
- Without the human study, we cannot yet say how RE:L!NK compares with a human planner on time or quality.
- Benchmark approvals are automated, so the benchmark measures planning quality, not approval behaviour.

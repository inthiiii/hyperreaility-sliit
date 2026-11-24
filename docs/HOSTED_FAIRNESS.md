# Priority Steps 3 and 4 — hosted execution and matched workflow comparison

**Owner:** Ihthisham Irshad. **Date:** 24 November 2026.

## Status and scope

This checkpoint implements the hosted request path and matched single-/multi-agent protocol together. Real OpenAI `gpt-6-luna` execution with reasoning `none` and the Responses API is verified on the demo. Development comparisons, failures and remaining quality limits are recorded in [LUNA_LIVE_VALIDATION.md](LUNA_LIVE_VALIDATION.md). Actual charges and independent held-out performance remain unverified; no superiority claim follows from a successful API check.

## Hosted execution

Each explicit Planning generation constructs a fresh coordinator and shared run budget. Passive browsing, mode selection, history inspection and rerenders make no model request. Hosted requests use the selected model, JSON-object response mode and a compact response schema; all replies undergo strict Pydantic validation. Unsupported settings, provider errors, missing/invalid usage, truncated responses and invalid facts cause a retained escalation/failure. One JSON repair attempt is permitted; automatic SDK retries are disabled. There is no silent template/model fallback.

Requests record provider, requested/returned model, request ID, role, prompt/schema/response hashes, output cap, actual token usage, finish reason, latency and sanitized error type/HTTP status. Provider exception bodies and credentials are not published. Reports remain untrusted evidence and cannot direct file access or dispatch. Approval remains a separate human action, bound to the plan/state content.

The unchanged automated benchmark whole-incident limits are **12 model calls, 24,000 input tokens, 4,800 output tokens and 180 seconds**, including repairs and event replans. Each explicit dashboard planning attempt has the same caps; an operator can explicitly start a separate attempt. Each solver invocation is capped at five seconds. The selected Responses path obtains an exact server-side input count for the same payload before generation. Legacy Chat Completions uses conservative UTF-8 bytes plus framing. Token-count requests are recorded as auxiliary requests, not generations; their latency consumes the same deadline. Count failure never silently falls back to an estimate. When valid usage arrives, actual consumed tokens replace that request's unused reservation; unknown-usage failures retain the reservation. Overspend is recorded and blocks approval, rather than becoming free usage. Conservative reservations can still stop a request before the provider's actual token limit would be reached.

## Matched baseline

| Stage | Single-agent workflow | Multi-agent workflow | Tools and information |
|---|---|---|---|
| Investigate | `single_agent` | `network_investigator` | Original visible reports, full operational context and typed fact output |
| Resources | `single_agent` | `field_resource_planner` | Same topology, observations, action options, skills, travel, windows and generator specifications |
| Priorities | `single_agent` | `service_priority_assessor` | Same services, approved weights, policy and shared findings |
| Review | `single_agent` | `plan_reviewer` | Same deterministic candidate, independent validation and operational context |

The normal successful path contains four calls in both modes. Both can request evidence revision, submit conservative action deferrals, use the same CP-SAT/heuristic tools, and access the same shared findings under the same caps. Single mode uses one agent identity; multi mode uses four role contexts. No hidden physical state or unreached event enters either prompt. Compact tabular encodings omit display coordinates/labels; every operational field used by the scheduling tools is available to both. The operational context hash records input parity.

This is a comparison of two controlled workflow configurations, not an experiment isolating agent count as the sole causal variable. Equal caps do not guarantee equal actual token consumption. Early safety escalations can use fewer stages. Three revision rounds are permitted, but the first exhausted whole-incident cap wins. Model generation temperature remains the provider default, recorded explicitly. The selected model uses explicit reasoning effort `none`; no unsupported seed is guessed.

## Agent influence on decisions

A resource/priority finding or scheduling revision can include a typed `defer_action` request with known action IDs, report/policy evidence IDs and a concrete reason. The coordinator validates the references, advances the state version, records the effect and excludes those actions from the next candidate. CP-SAT may select a different feasible allocation; deferred fault options remain visible as unmet needs. The independent validator still checks feasibility, and the coordinator separately checks that no deferred action was scheduled. The dashboard shows the requesting agent, actions, reason and evidence before human approval.

These requests are conservative model judgments, not independently verified physical facts. They cannot change approved service weights, authorize execution, edit resources or patch evaluator truth. Holds apply to the current planning/revision attempt; a new incident checkpoint is reassessed and requires fresh approval. They are not persistent operator-confirmed restrictions. A bad hold can reduce restoration quality and must be judged by the same simulator. A known evidence conflict still requires operator clarification; agent agreement cannot resolve it. Typed request effects prove that a role can influence the result, not that its influence improves it.

Reviewer-removal ablation omits the final review stage. No-feedback ablation removes shared agent findings and blocks requests/revision rather than silently ignoring a requested safety hold. These ablations intentionally differ from the full matched workflow and are identified separately in the manifest.

## Evaluation artifacts

- `manifest.json`: source/input fingerprints, exact requested model/provider, endpoint fingerprint, generation/retry settings, protocol/tasks hash, package/runtime/hardware metadata, shuffle seed and incident caps.
- `attempts.jsonl` / `attempts.csv`: every job, status, usage, returned model versions, decision-effect count, runtime and final independent scores when complete.
- `runs/`: checksummed run traces and raw agent messages, including extraction output before deterministic fill-in.
- `simulations/`: separate automated benchmark approvals and independently measured episode artifacts.
- `comparison.json`: paired single-minus-multi downtime, wins/ties, coverage/exclusions, failure counts, effects and exploratory paired bootstrap interval when at least two comparable pairs exist.

Configuration is frozen at experiment start and checked before every hosted episode. Drift fails the affected attempt before constructing a new adapter. A scored pair is pooled only when both variants complete with matching configuration and exactly one identical provider-returned model version. Missing, mixed or mismatched versions are excluded. Unscored cases retain null downtime and appear in coverage/failure counts. API charge remains null; token totals are not currency.

Raw extraction precision/recall/F1 uses recognized fixture sentence labels before the resolver fills omitted authoritative facts. It reports labelled/unlabelled coverage and must not be described as F1 over independently audited natural-language or held-out cases. Development repetitions are not independent new scenarios; the bootstrap interval is exploratory. Independent case review, participant benchmarking and final release evidence remain later priorities.

## Run commands

```sh
source .venv/bin/activate
python -m pytest -q
python -m streamlit run project/main.py
```

For a bounded real verification, use the selected model and API settings below. Keep the API key in the existing local `.env` file. This command does not edit it or publish its contents:

```sh
python -m project.evaluation.hosted_check \
  --model gpt-6-luna \
  --reasoning-effort none --api-mode responses \
  --env-file .env \
  --output results/local_benchmarks/hosted-check-01 \
  --allow-live
```

This runs **two development attempts**, single and multi, once each on DEMO-005. Each receives the stated whole-incident caps; worst-case experiment totals are twice those caps. Charges are possible. Existing output directories/files are never overwritten. A nonzero exit retains failures for inspection. To use a key stored in another checkout, pass that file explicitly with `--env-file`; never copy the key into the command.

For broader development comparison, configure `.env` and use the existing runner with development-only inputs:

```sh
python -m project.evaluation.runner \
  --scenarios data/processed/agent_inputs/demo/DEMO-005.json \
              data/processed/agent_inputs/development/DEV-010.json \
  --variants heuristic optimizer single multi no_reviewer no_feedback \
  --repeats 3 --allow-live \
  --output results/local_benchmarks/development-comparison-01
```

Do not treat development fixtures, injected clients or unreviewed evaluation candidates as a finalized held-out study. Select/freeze the model on development cases before the later independent evaluation milestone.

## Authorship and assistance

The initial matched-protocol commit was prepared for Ihthisham's core/coordinator workstream with ChatGPT/Codex assistance. The later joint Luna verification commit credits Ihthisham, Zahra, Eyaas and Kiruthika at the user's request.

## Actual verification at this checkpoint

- Full repository regression: **411 passed in 42.65 seconds**.
- Offline CLI: four attempts, four independently scored outcomes, zero model calls. Static DEMO-005 and resumed DEV-010 measurements retain the earlier scoring semantics.
- Injected-client tests cover equal four-stage access/caps, changed validated schedules from resource/priority/reviewer requests, hallucinated references, disabled-feedback behavior, model drift, mixed returned models, raw-extraction scoring, reservation reconciliation and overspend retention.
- Streamlit AppTest verifies visible deferral reasons, a fresh unapproved candidate, and simulation blocked until an operator supplies approval.
- Installed SDK inspection confirms the request parameters used by the adapter exist. This is parameter compatibility checking, not provider verification.
- The later Luna validation checkpoint supersedes the initial pending-live status; see LUNA_LIVE_VALIDATION.md for provider results.

## Selected-model follow-up

The joint Luna checkpoint uses protocol `matched-workflow-v4`, which makes repair semantics, the weighted-availability objective and the approval-before-simulation boundary explicit in both modes. In particular, equipment repair cannot restore grid power. Input-token counting is exact on the selected Responses path; auxiliary count requests and generations are audited separately. Regression tests disable personal `.env` loading and provider credentials. Team co-author attribution is attached to the joint follow-up commit at the user's request.

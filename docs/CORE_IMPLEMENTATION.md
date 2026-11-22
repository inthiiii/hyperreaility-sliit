# Core implementation handoff

Implemented 22 November 2026 in an isolated checkout because the coding session could read but could not write the user's Documents checkout. No original-folder files, credentials, data preprocessing, dashboard or submitted proposal were overwritten. The delivery patch applies these source changes to the original checkout after a normal Git patch check.

## What works

- Strict version 0.1 scenario and shared output contracts compatible with the starter processed fixtures.
- Conservative evidence resolution with report citations and conflict/missing-evidence escalation.
- Independent physical schedule validation: IDs/catalogue, timing, travel routes, closed/unknown roads, skills, crew overlap and generator allocation/transport.
- An earliest-finish feasible heuristic and a time-indexed CP-SAT scheduler with crew routing, service dependencies and temporary generator power.
- A bounded coordinator with explicit template, hosted single-agent and hosted four-role modes. Both hosted modes can review and request evidence revisions within the same whole-run limits. A reviewer is not operator approval.
- A hosted adapter for explicitly configured OpenAI/OpenRouter model IDs, aggregate budget reservation, one JSON-schema retry, usage/error records and no silent provider/model fallback in application code.
- Approval bound to exact plan/state content hashes.

Read `docs/DATA_CONTRACT.md` before connecting a loader, dashboard or simulator.

## Run now without a key

From the repository root with the existing virtual environment active:

```sh
python -m pytest tests/core -q
python -m project.core.demo --scenario tests/core/fixtures/DEMO-005.json --mode template --output /tmp/relink-core-demo.json
```

Template mode matches only the supplied fixture sentences. It is a deterministic development baseline, **not a live model or multi-agent demonstration**. The expected core result is awaiting_approval, one generator deployment at S02 completing at minute 30, zero model calls and predicted 720 weighted available service-minutes (5760 weighted downtime) over the static horizon. The runner does not simulate or dispatch the plan.

Tests use six visible scenario fixtures copied from the previously generated team starter pack. They contain no evaluator answers. They are development fixtures, never held-out benchmark cases.

## Hosted modes for later explicit testing

The starter application's dotenv template already defines LLM_PROVIDER, LLM_MODEL, OPENAI_API_KEY, OPENROUTER_API_KEY and LLM_BASE_URL. Configure these **locally** with an exact available model ID. Do not commit populated configuration. Example invocation, which DOES send inference requests once configured:

```sh
python -m project.core.demo --scenario tests/core/fixtures/DEMO-005.json --mode single --output /tmp/relink-single.json
python -m project.core.demo --scenario tests/core/fixtures/DEMO-005.json --mode multi --output /tmp/relink-multi.json
```

Both modes use the same graph/scheduling/validation tools, fixed approved weights and typed data. Four roles exchange structured findings and reviewed evidence through the coordinator. Resource/Priority findings can trigger clarification; they do not silently change the approved policy. Revisions re-extract facts, version state and rebuild/validate the schedule. Specialist feasibility claims never override the independent validator. Both modes receive physical state/tool output during review; benchmark workload, prompt/context settings and tool parity still require a frozen evaluation protocol.

No hosted requests or spend were performed during implementation. Adapter tests inject fake provider responses. The installed OpenAI SDK signatures were checked for the request parameters; actual model availability, account quota and response quality remain unverified. This session's proxy environment also lacks optional SOCKS transport support; if that same issue occurs in a user's configured proxy environment, resolve the proxy dependency before attempting hosted calls. No proxy settings were bypassed.

## Budgets and failures

Whole-run defaults are 12 calls, 24000 input and 4800 output tokens, and 180 seconds. All JSON repairs consume the shared allowance. Input reservations use conservative UTF-8 byte counts plus framing; output reservations use the requested maximum. This may stop a run earlier than actual token usage would require. Actual reported token usage, request/model IDs, errors and latency are recorded separately. Provider responses with missing usage or incomplete output fail closed. Automatic transport retries are disabled, avoiding uncounted SDK retries; transient failures currently escalate instead of retrying.

A CP-SAT attempt is capped at five seconds with one worker and a recorded seed. Solver failure/timeout without a usable result falls back explicitly to the labelled greedy baseline. Model-adapter failure never silently falls back to template mode. The coordinator's result and usage records are returned for persistence; durable JSONL/SQLite storage, authenticated operator accounts and UI session binding remain integration work.

## Work for teammates and remaining integration

- Zahra: loader and independent simulator, including generator expiry and timed world events. Use `check_approval` with current state before simulation. Implement independent metrics; do not reuse the planner's claimed score.
- Eyaas: replace the environment screen with the agreed dashboard and coordinator calls; prevent rerender API calls, capture operator identity and invalidate approvals on updates.
- Kiruthika: manual QA and reproducible defects, with actual outcomes.
- Ihthisham: integrate remaining event/replanning lifecycle and histories with Zahra; durable traces; model settings frozen for evaluation; update status docs with real results.

Static snapshots are implemented; in-progress work/resumption and crew-loss event execution are not. Unknown evidence currently escalates globally. CP-SAT supports rooted trees and five-minute-aligned inputs, not arbitrary network meshes or a detailed fuel model. No measured benchmark improvement, human study, general field-message robustness or production readiness is claimed.

## Verification

The automated core suite tests contract rejection, uncertainty/conflict/stale evidence, solver outputs, independent validation failures, content-bound approval, coordinator exchanges, bounded revisions, schema repair and budget exhaustion. See the latest handoff for the recorded run. AI assistance: ChatGPT/Codex generated and exercised these core modules; hosted OpenAI/OpenRouter calls were not used. Add this assistance and all actual future model IDs to the project's disclosure register before submission.

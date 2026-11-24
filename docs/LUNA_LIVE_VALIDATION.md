# Priority Steps 3 and 4 — live Luna verification

**Date:** 24 November 2026. **Team:** Ihthisham Irshad, Zahra Hassan, Eyaas Ajmal and Kiruthika Vijayakumar.

## What is implemented and verified

The application now uses OpenAI `gpt-6-luna`, explicit reasoning effort `none`, and the Responses API. Both the single-agent and four-role workflows have completed real hosted demo runs followed by approval-gated independent simulation. A separate dashboard rehearsal showed all four role exchanges, four actual generations, a validated candidate, simulation blocked before approval, and a matching result after an explicitly labelled synthetic rehearsal approval.

Full automated regression: **428 passed in 43.08 seconds**. Five report-aggregation tests were also rerun after adding escalation-category and per-variant extraction summaries. Tests explicitly disable personal `.env` loading and clear provider credentials; live runs are separate explicit commands.

Inspect the published [demo summary](../results/development/luna-live-smoke/summary.json), [single-agent trace](../results/development/luna-live-smoke/single.json), [multi-agent trace](../results/development/luna-live-smoke/multi.json), and [dashboard proof](../results/development/luna-live-smoke/dashboard.jpg). These are real provider responses on a synthetic demo, not fake-client results or real operator outages. Demo weighted downtime was **5760 weighted service-minutes** in both modes, measured over the complete simulator horizon.

## Implementation changes

- Selected model, reasoning effort and API transport are explicit, validated, included in UI request identity, recorded in usage, and frozen in experiment manifests. Configuration drift fails closed.
- On the selected Responses path, the same model/input/text-format/reasoning payload is submitted to OpenAI's input-token counter before generation. Exact counts replace the older byte reservation. Counter failures do not silently fall back to an estimate.
- Token-count requests have separate audits and counts. They are not model generations, but their latency consumes the same deadline. Responses are requested with `store=False`.
- The limits remain 12 generations, 24,000 input tokens, 4,800 output tokens and 180 seconds per automated benchmark incident, including continuation. Dashboard limits apply per explicit planning attempt. Solver calls remain capped at five seconds.
- Both workflows receive the same operational context, repair semantics, approved objective and tools. Equipment repair does not restore grid power. Reviewer approval means ready for human review and subsequent simulation; it never establishes actual restoration.
- Evidence-linked action holds can change the candidate action space and state version. Independent validation and separate operator approval remain mandatory.
- SOCKS proxy support is an optional dependency in `project/requirements-proxy.txt`. The existing Documents checkout and its credentials were not overwritten.

OpenAI documentation: [Luna model](https://developers.openai.com/api/docs/models/gpt-6-luna) and [input-token counting](https://developers.openai.com/api/docs/guides/token-counting). The installed SDK's supported parameters and the real endpoint behavior were both checked.

## Development comparison actually run

Ten development scenarios, three repetitions, and four variants produced **120 completed attempts**. The variants were tool-assisted single agent, full multi-agent workflow, reviewer removal, and disabled feedback. Ten disjoint one-case batches ran concurrently; both compared workflows were interleaved within each batch. Wall times include contention and are not isolated latency benchmarks. The model does not use a supported sampling seed; the order and solver seeds are recorded.

| Variant | Fully scored incidents | Escalated/unscored | Total attempts |
|---|---:|---:|---:|
| Single agent | 15 | 15 | 30 |
| Multi-agent | 14 | 16 | 30 |
| Without reviewer | 20 | 10 | 30 |
| Without feedback | 12 | 18 | 30 |

There were **61 full-horizon scores and 59 escalations**. No escalation received an invented downtime score. Escalations include actual uncertainty, model review/clarification, invalid model claims, API errors and budget stops; they are not all verified-correct safety decisions. The JSON report separates these categories. Some dynamic cases stopped after a partial incident and remain unscored.

Only **11 of 30** matched single/multi pairs were complete and comparable. **All eleven tied** on weighted downtime. The other 19 pairs are retained as exclusions with coverage counts. Unmatched means over different scored cases must not be used to claim a quality difference. These development results **do not demonstrate a multi-agent restoration advantage**; reviewer removal's higher completion count is also not evidence of better semantic safety.

Raw initial extraction is scored before the resolver adds recognized authoritative fixture facts:

| Variant | Raw fixture extraction micro-F1 |
|---|---:|
| Single agent | 100% |
| Multi-agent | **100%** |
| Without reviewer | 100% |
| Without feedback | 100% |

The full multi-agent workflow meets the planned 90% target **on recognized labelled fixture claims in this development cohort**. Across 132 metric-bearing run records, raw extraction produced 228 true positives, zero false positives and zero false negatives. Twelve unlabelled reports were outside this metric. Labels cover recognized visible fixture sentences, not an independently audited natural-language dataset; repeated runs and repeated incident reports are not independent new examples. This is not a claim of 100% real-world accuracy.

Inspect the complete [comparison report](../results/development/luna-v4-development-20261124/report.md) and [machine-readable outcomes](../results/development/luna-v4-development-20261124/report.json). They retain every job, source/input/configuration fingerprints, failure coverage, returned models and the paired comparison. Raw full-batch traces remain under ignored local benchmark directories; their file hashes are in the public report. Actual API charges were not measured; incomplete usage remains unavailable rather than zero.

## Live influence on a validated candidate

Regression tests prove that typed resource, priority and reviewer requests can change a validated schedule while retaining policy and approval boundaries. The earlier v3 cohort applied resource holds, but its [offline counterfactual audit](../results/development/luna-development-20261124/influence_audit.json) showed no changed allocation; it did not establish a realized benefit.

The v4 [modified-demo permit challenge](../results/development/luna-live-influence-v4/summary.json) demonstrated the missing causal path. A confirmed operational report stated that the generator-placement permit at S02 was not issued. The Resource Planner emitted a typed `defer_action` for `GEN-G1-S02`, cited `PERMIT-S02`, and advanced the state version. The candidate changed from `GEN-G1-S02` to `GEN-G1-S01` plus `BH-L01`, and independent encoded feasibility validation passed. The unconstrained counterfactual used the same input and resolved facts.

The Reviewer then escalated for a revision without a concrete request. The candidate was therefore **not approved or simulated**. This verifies live influence on a validated candidate, not full-incident success, physical permit enforcement, a restoration benefit or a reason to bypass review. Inspect the [input](../results/development/luna-live-influence-v4/input.json) and [actual role trace](../results/development/luna-live-influence-v4/run.json). It is a modified-demo engineering challenge outside the registered ten-case comparison. The earlier [unsuccessful v3 challenge](../results/development/luna-live-influence/summary.json) is also retained.

The selected operational protocol is now `matched-workflow-v4`. A separate [successful current-protocol multi-agent example](../results/development/luna-v4-live-example/multi.json) and [measured summary](../results/development/luna-v4-live-example/summary.json) are published. The dashboard/demo smoke artifacts above predate the final report-level prompt refinement and verify the same API/UI/approval integration.

## Diagnostic work retained

The first setup attempt made zero generations because SOCKS support was absent. Initial hosted demo runs exposed reviewer confusion over the approval/simulation order and repair semantics; those stops were retained, not reported as successful scores. After clarifying the shared contract, both demo workflows completed.

A first full Chat Completions development round produced 44 scores from 120 attempts; conservative byte reservations stopped otherwise affordable calls. Its [diagnostic report](../results/development/luna-diagnostic-20261124/report.md) remains separate from the final Responses cohort. The rounds are not pooled or treated as a controlled causal experiment. The [v3 exact-counting Responses cohort](../results/development/luna-development-20261124/report.md) produced 53 scores from 120 attempts and a full-multi extraction F1 of 89.09%. The final v4 instructions preserve each report claim separately, retain source-specific verification and require actionable restrictions as typed requests. Its cohort produced 61 scores from 120 attempts; no superiority or general improvement conclusion follows from that difference alone.

## What completion means here

Priority Step 3's live integration and Step 4's matched evaluation infrastructure, actual development comparison and live influence on a validated candidate are delivered. The labelled-development extraction target is met. This is **not submission readiness or evidence that every quality gate passes**: many incidents still escalated, the permit challenge did not pass final review, and no measured multi-agent restoration advantage was observed. These remain material operational/quality limitations. Do not force approval, remove uncertainty, relabel failures, or switch models silently to improve the numbers.

Independent case review (Priority 5), full manual QA/demo rehearsal (6), and final comparison/release evidence (7) remain separate. No held-out benchmark or human participant study was run for this checkpoint.

## Reproduce

Keep the existing API key private and set:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-6-luna
LLM_REASONING_EFFORT=none
LLM_API=responses
```

```sh
python -m pytest -q
python -m project.evaluation.hosted_check --model gpt-6-luna --reasoning-effort none --api-mode responses --env-file .env --output results/local_benchmarks/luna-smoke-new --allow-live
python -m streamlit run project/main.py
```

Use a new result directory for each run. For the ten-case comparison use the documented runner with development inputs and `--variants single multi no_reviewer no_feedback --repeats 3 --allow-live`. The published manifest/artifact list identifies the ten case batches. `scripts/report_development.py` aggregates complete, disjoint, matching batches and rejects source/configuration mismatches, duplicates, incomplete jobs and held-out case labels.

Prepared with ChatGPT/Codex assistance in Ihthisham's session. The joint checkpoint credits all four team members as requested. Coding-assistant authorship is separate from the runtime Luna agents.

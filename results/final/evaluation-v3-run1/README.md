# Held-out benchmark (EVAL2, evidence v3): results

Run on 25 Nov 2026 (UTC) under the configuration freeze `releases/evidence-v3-20261126/FREEZE.json` (commit `524945f`), so no setting was changed after the cases were seen.

| Setting | Value |
|---|---|
| Cases | 20 held-out EVAL2 cases, 2 per category |
| Variants | 6: heuristic, CP-SAT (`optimizer`), `single`, `multi`, `no_reviewer`, `no_feedback` |
| Repeats | 3 per case and variant |
| Attempts | 360 in total (240 with the model), run in a seeded, interleaved order |
| Model | `gpt-6-luna`, Responses API, reasoning `none` |
| Caps per incident | 12 calls, 24k input / 4.8k output tokens, 180 s |

The full generated tables are in [REPORT.md](REPORT.md), with per-case values in [per_case.csv](per_case.csv), machine-readable numbers in [summary_report.json](summary_report.json) and raw rows in [attempts.jsonl](attempts.jsonl).

> Synthetic, script-generated cases; not independently reviewed by a person. Downtime is weighted service-minutes over 12 hours, measured by the independent simulator (lower is better). Escalated attempts are not scored.

## Main findings

**1. Agents reading the reports cut downtime compared with optimisation alone.**

| Comparison (per-case medians) | Agent better | Tie | Worse | Mean difference | 95 % CI (bootstrap over cases) |
|---|---:|---:|---:|---:|---|
| Multi-agent vs CP-SAT without AI | 13 | 7 | 0 | −2,378 | −4,044 to −981 |
| Single agent vs CP-SAT without AI | 11 | 8 | 0 | −1,811 | −3,334 to −636 |

Median relative change: −12.5 % across all cases (ties included), and about −17 % on the 14 cases where the plans differ. Without agents, CP-SAT cannot use free-text alarms and messages, so faults that only reports reveal stay unrepaired.

**2. Multi-agent vs single agent: no significant difference in downtime.**

| | Multi better | Tie | Single better | Mean (multi − single) | 95 % CI |
|---|---:|---:|---:|---:|---|
| 19 shared cases | 2 | 15 | 2 | −199 | −596 to 57 |

- Multi was clearly better on EVAL2-010 (475 vs 3,600) and EVAL2-019 (4,930 vs 6,215). Single was better on EVAL2-004 and EVAL2-017.
- The interval includes zero, so the proposal's target (≥ 10 % median reduction against single) is **not met**. No multi-agent superiority is claimed.

**3. Reliability and cost**

| Variant | Completed | Escalation causes | Calls | Input / output tokens | Seconds |
|---|---:|---|---:|---|---:|
| multi | 54/60 | 4 truncated Reviewer answers, 1 provider safety filter (at the Reviewer call), 1 budget | 4.9 | 13.3k / 1.2k | 17.8 |
| single | 53/60 | 5 budget (growing single context), 2 truncated first analyses | 2.3 | 11.3k / 1.0k | 11.9 |
| no_reviewer | **60/60** | none | 3.3 | 8.7k / 0.8k | 12.3 |
| no_feedback | 49/60 | 8 revision requested (by design), 2 truncated Reviewer answers, 1 safety filter (at the Reviewer call) | 4.3 | 11.7k / 1.0k | 15.9 |
| heuristic, CP-SAT | 60/60 | none | 0 | 0 | < 1 |

**4. The Plan Reviewer did not earn its cost on this set.**

- Downtime: multi vs no_reviewer gives 1 better, 17 ties, 2 worse (95 % CI −193 to 72).
- Reviewer fact challenges happened in 11 runs: they improved extraction in 3 and made it worse in 3.
- The Reviewer adds about 50 % more tokens. 5 of the 6 multi-agent escalations happened at the Reviewer's call (4 truncated answers and 1 safety-filter rejection).
- The most reliable and cheapest agent configuration was **multi-agent without the Reviewer**.

**5. Safety**

- Prompt-injection reports were never followed: 0 of 130 runs that contained one.
- Claims citing distractor reports were near zero (≤ 0.04 per run).
- In 2 runs OpenAI's safety filter rejected the request (HTTP 400). The cause is not known: one of the two cases contained the planted injection message and the other did not. A production system must handle such rejections gracefully.

**6. Extraction quality:** initial fact F1 was 0.88–0.96 across agent variants. Runs with F1 below 0.8 concentrate in EVAL2-006, -016 and -019 (16 of 28 such runs).

## Honest interpretation

- The value shown here comes from **agents that read messy evidence**, not from having more agents.
- Splitting the work across specialists gives a modular, cheaper-per-call design that completed slightly more cases than one large context. But the independent Reviewer as designed adds cost without improving outcomes on these cases.
- These conclusions hold for this synthetic set and this model only.

## Limits

- 20 synthetic cases from a phrase-bank generator, with no independent human review.
- One model; 3 repeats.
- Cost in USD is not included until the team supplies dated per-token prices.
- Escalated attempts are unscored, so comparisons use only cases where both variants have a median.
- The human comparison is pending.

## Possible next steps (not applied to this run)

These would need a new freeze and a new held-out run:

- Raise the output caps that truncated answers.
- Trigger the Reviewer only when the evidence is risky (contradictions, low-authority claims).
- Strip injection text before the provider sees it, or retry once with it quoted.

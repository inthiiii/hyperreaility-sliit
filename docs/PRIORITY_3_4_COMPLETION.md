# Priority Steps 3 and 4 — completion update

**25 November 2026 · RE:L!NK · HyperReAIlity**

## Delivered scope

**Step 3 — hosted execution:** OpenAI `gpt-6-luna`, reasoning `none`, Responses
API, exact input counting, strict response schemas and local semantic validation.
The four roles remain Network Investigator, Field Resource Planner, Service
Priority Assessor and Plan Reviewer. CP-SAT, validation and service forecasting
are deterministic tools, not extra LLM agents. Single-agent mode traverses the
same four stages with one identity.

**Step 4 — matched development evaluation:** same operational information,
response allowances, tools and whole-incident caps; real hosted comparisons,
raw initial-extraction scoring, independent full-horizon simulation and explicit
coverage/exclusions. Evidence-linked role requests can change the candidate;
policy weights and evaluator truth cannot be changed by agents.

This is completion of the implementation and development-verification scope.
It does not certify reliable autonomous operation, a winning submission or a
measured multi-agent advantage. Human approval remains mandatory.

## Concrete gaps fixed

1. **Reviewer ambiguity:** an unusable revision receives bounded clarification
   with the exact visible evidence/arithmetic. The unchanged candidate is reused;
   a model must explicitly approve or the workflow escalates. No automatic approval.
2. **New holds after approval:** any newly requested deferral creates a fresh
   state/candidate, validation and explicit review. Existing holds may be
   acknowledged without inventing another revision.
3. **Token framing:** lossless action codebooks/CSV and complete-snapshot encoding
   reduce repetition. Original report text, topology, inventory, timings, policy,
   all action fields and explicit unknowns remain available to both modes.
4. **Service-minute interpretation:** review receives per-service visible-state
   forecasting and exact work-end arithmetic, making travel timing and the network total
   explicit rather than attributing all availability to one generator. This forecast is
   labelled prediction; independent simulation remains the measurement source.
5. **Structured output and diagnostics:** native strict schemas constrain evidence
   references to supplied IDs. Local validation rejects invented actions/evidence;
   rejected typed outputs and redacted provider errors are retained for audit.
6. **No-report incidents:** empty evidence no longer creates contradictory schema
   bounds. Focused live checks in both modes return the genuine missing S01
   equipment fact after one valid investigator response, rather than provider 500.

## Validation and boundaries

Full automated regression: **458 passed in 43.87 seconds**. Includes data/simulation, core,
evaluation, Streamlit UI/service checks, lossless encoding round-trips,
reviewer clarification, hold acknowledgment, fresh review after new holds,
invalid-reference rejection, no-feedback behavior and stale approval protections.
Tests cannot load the personal provider key. Forecast arithmetic was also checked
against scheduler predictions on all eight resolvable development fixtures.

The current protocol is `matched-workflow-v13`. Limits remain **12 generations,
24,000 input tokens, 4,800 output tokens and 180 seconds per incident**, including
continuation; solver calls remain at most five seconds. Per-stage output allowances
are 700/450/450/500 tokens for investigation/resources/priorities/review in both
modes. Auxiliary token-count calls consume the same deadline and are separately
audited. No fallback model or raised incident cap was used.

## Current live development comparison

The [v13 repeated-run report](../results/development/luna-v13-development-20261125/report.md)
and [all machine-readable outcomes](../results/development/luna-v13-development-20261125/report.json)
cover **10 development cases × 3 repetitions × 4 variants = 120 attempts**.
Ten disjoint case batches ran concurrently, interleaving variants within each
batch. Latency includes contention; this is not an isolated speed benchmark.

| Variant | Full-horizon scores | Escalated/unscored | Attempts |
|---|---:|---:|---:|
| single | 16 | 14 | 30 |
| multi | 12 | 18 | 30 |
| no_reviewer | 17 | 13 | 30 |
| no_feedback | 12 | 18 | 30 |

There were **57 full-horizon scores and 63 escalations**. Of thirty eligible
single/multi pairs, twelve were complete/comparable and **all twelve tied** on
weighted downtime. Eighteen pairs remain excluded, with their failures retained.
Full multi completed 12/30 incidents versus single's 16/30. The current evidence
therefore does not justify a multi-agent performance advantage. Means over
differing scored case sets are not a fair quality comparison. Escalated incidents
never receive invented scores; they are not all independently verified correct
safety decisions.

Raw initial-extraction micro-F1 was **100% on recognized labelled fixture claims**
in each variant: 222 true positives, zero false positives/negatives over 129
metric-bearing run records. Nine unlabelled reports were outside this metric.
Repeated reports are not independent natural-language examples. This meets the
labelled-development target only; no real-world accuracy or held-out claim follows.
No participant study was used.

Before this repeated comparison, a separate
[40-attempt current-source verification pass](../results/development/luna-v13-verification-20261125/report.md)
produced 19 scores/21 escalations, with four comparable single/multi pairs all tied.
It is retained separately rather than pooled as extra independent scenarios.
[Selected examples from that pass](../results/development/luna-v13-examples-20261125/summary.json)
include scored single/multi incidents with independent simulator artifacts,
no-report evidence escalations and unsuccessful dynamic continuation traces.
Both v13 reports' source fingerprints match the current runtime source. Actual
API charges were not measured; available usage/failure information is retained.

## Diagnostics and remaining limitations

The separate [v12 diagnostic cohort](../results/development/luna-v12-diagnostic-20261125/report.md)
has 120 attempts (ten cases × three repetitions × four variants): 53 full-horizon
scores and 67 escalations. Its nine comparable single/multi pairs all tied.
It exposed the empty-evidence schema error, fixed before the v13 pass. It uses a
different source/protocol and must not be pooled with v13 or older v4 results.
The repeated v13 comparison fulfills the three-run development check, not the
later independent held-out evaluation. Cross-cohort count changes do not prove improvement.

The [diagnostic record](../results/development/luna-review-diagnostics-20261125/report.json)
retains eight focused protocol rounds, three permit trials, the no-report fix
confirmation and an initial unattached batch that made zero generations because
its token-count requests encountered connection errors. The latter is excluded
from the actual model comparison, not silently deleted.

A [v5 permit trial](../results/development/luna-review-diagnostics-20261125/permit-1/summary.json)
produced a typed hold, changed the independently validated schedule and passed the
approval gate for an explicitly automated test operator. It was not physically
simulated. Both [v12 repeat 1](../results/development/luna-review-diagnostics-20261125/permit-2/summary.json)
and [repeat 2](../results/development/luna-review-diagnostics-20261125/permit-3/summary.json)
stopped for specialist clarification before a candidate was emitted. That earlier
success is not evidence of reliable current-protocol performance.

**Material limits remain:** specialists sometimes treat known constraints or
unmet restoration needs as missing information. Dynamic DEV-010 did not complete
in either reviewed single/multi workflow; two of three reviewer-removal attempts
completed, which does not establish semantic safety. The final comparison has
eleven workflow-exception/budget escalations across variants, alongside unresolved
evidence and model clarification.
These are not all independently verified correct safety decisions. Native schema
bounds do not replace semantic validation. The new audit retains rejected output
for diagnosis, and approval cannot bypass these stops.

No measured multi-agent restoration advantage, reliable permit handling, general
100% extraction accuracy, production outage reduction or financial saving is
claimed. Further model/protocol tuning should be evaluated as a new development
cohort before freezing the later independent evaluation.


## Reproduction

Keep the existing API key private in the ignored `.env` file:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-6-luna
LLM_REASONING_EFFORT=none
LLM_API=responses
```

```sh
python -m pytest -q
python -m project.evaluation.runner \
  --scenarios data/processed/agent_inputs/development/DEV-001.json \
  --variants single multi no_reviewer no_feedback \
  --repeats 3 --allow-live \
  --output results/local_benchmarks/new-development-check
python -m streamlit run project/main.py
```

Use new output directories; never overwrite experimental evidence. Run the same
command for DEV-002 through DEV-010 and aggregate disjoint matching batches with
`scripts/report_development.py`. The final repeated comparison uses three repetitions
per case/variant; the earlier v12 diagnostic and one-repeat v13 verification
cohorts are separate.
The later independent evaluation can use the proposed repeated-run design after
model/protocol freeze. Do not run held-out cases as development examples.

## Handoff and attribution

The update is prepared with ChatGPT/Codex in Ihthisham's session, with requested
co-author credit for **Ihthisham Irshad, Zahra Hassan, Eyaas Ajmal and Kiruthika
Vijayakumar**. Coding assistance is separate from runtime Luna model usage.

Review the pull request before merging. Stop here: independent case review
(Priority 5), complete manual QA/demo rehearsal (6), and final comparison/release
(7) remain later milestones. No participant study or held-out benchmark was run.

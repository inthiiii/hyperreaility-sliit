# Zahra delivery handoff: preprocessing, independent simulation and continuation

Updated 24 November 2026. Branch: `feature/zahra-completion`.
Zahra's original starter-data commit `53fa58a` and implementation `13b00ea`
are preserved as merge ancestry (`cbd1d2e` integrates current main). Continuation
commits retain Ihthisham's configured Git identity and the requested trailer:
`Co-authored-by: Zahra Hassan <zahrahasan2163@gmail.com>`.

## Delivered software

- Public Sri Lanka geographic context (25 districts, three Western districts),
  retained source/license metadata and attribution; no real telecom inventory.
- One five-site demo, ten development cases, twenty draft evaluation candidates.
  Raw snapshots remain unchanged. JSON is authoritative; nulls and contradictory,
  stale and missing evidence remain explicit.
- Reproducible preparation, strict file/byte/hash validation (201 files), an
  automated structural/literal-label audit and a frozen candidate-release snapshot.
- Allowlisted typed input loader with filename/ID consistency, path/symlink escape
  rejection and field-level errors that do not echo invalid input values.
- Separate evaluator loader. Models, agents and the core never import it or see
  hidden future events. `project.data.audit` is evaluator-side tooling only.
- Independent static simulation, generator transport/deployment/depletion,
  equipment/link repairs, full upstream dependency checks and deterministic
  service metrics. No planner prediction is used as a measured outcome.
- Persistent evaluator-side `IncidentEpisode`: pause at resource observations,
  retain work, locations, fuel timers and elapsed metrics, accept a new visible
  checkpoint, require a higher state version and a freshly approved plan, then
  continue the same incident to minute 720.
- Dashboard attachment, source freshness checks, operator decisions, partial-result
  labeling, continuation controls, measured intervals/action outcomes, history and
  exports. Scenario changes clear live authorization and incident state.

## Exact run commands

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r project/requirements.txt
python scripts/check_data.py
python -m pytest -q
python -m streamlit run project/main.py
```

No extra dependency was introduced. Tested on the team's macOS/Python 3.11
virtual environment using the existing pinned dependencies. No hosted inference,
paid API, network download or local LLM is used by this delivery verification.

To reproduce the audit/smoke checks without overwriting retained evidence:

```bash
python -m project.data.audit --output /tmp/relink-data-audit-new.json
python -m scripts.verify_delivery --output /tmp/relink-delivery-smoke-new.json
```

Outputs use exclusive creation; choose a new path if one exists. Published audit
and smoke records are under `docs/evaluation/`. `FROZEN_DATASET.json` is an
immutable working-candidate snapshot, NOT proof of independent held-out validity.
The generation, preparation and download scripts refuse to overwrite this frozen
release. For subsequent dataset changes, create a separately reviewed release in
a new branch/directory; preserve this release and its hashes. Do not remove the
freeze merely to make a failing checksum check pass.

## Interfaces and operational semantics

```python
from project.data.loader import load_case
from project.data.evaluator import EvaluatorLoader  # evaluator harness only
from project.simulation.episode import IncidentEpisode

scenario = load_case('development/DEV-010.json')
episode = IncidentEpisode(scenario, EvaluatorLoader().load(scenario.scenario_id))
# Supply a genuinely reviewed plan, its matching approval and verified state:
result = episode.advance(scenario, plan, approval, state=verified_state)
if episode.paused:
    visible_update = episode.checkpoint()
    # Core prepares a new state/plan; operator approves it before the next advance.
```

`simulate(scenario, plan, approval, isolated_truth, state=...)` supports static
runs and returns a prefix result for an eventful run. Use IncidentEpisode or
`session_callback(core_session, truth_loader)` for continuation; the callback has
a `checkpoint()` accessor for its safe visible snapshot. Never create a fresh
simulator at each replan and score the elapsed interval again.

Actions finishing at the event minute complete first. The lost crew's unfinished
work gets no partial repair credit and must restart if rescheduled. Only
unaffected work already departed continues under its original approval; later
scheduled departures are cancelled for fresh review. Such a committed crew is
reserved until its already-approved work ends; its projected destination is not
available early. A lost crew's in-transit position is the last reached node and
cannot authorize further travel. A collected generator lost before deployment
is unavailable; recovery/refuelling/redeployment remain outside the one-deployment
MVP. Generator expiry is measured by the evaluator. A replan sees only the public
resource specification's expected expiry and observations already reached, not
unobserved private future resource values.

`ScenarioInput.active_generators` is an optional backwards-compatible field for
observed running deployments and expected expiry. The CP-SAT tool accounts for
these during the remaining horizon and cannot redeploy unavailable generators.
`simulated_completion` reports record completed approved work as a new physical
state; they do not resolve unrelated contradictory reports by recency.

At a pause, `measurement_scope=elapsed_prefix`, `observed_until_min` is the stop
minute, full-horizon availability/downtime/end-state fields are null, and explicit
`*_so_far_min` values measure the prefix. At final completion,
`measurement_scope=complete_incident` and metrics integrate exactly over [0,720).
Events at minute 720 affect final state but add no positive-duration availability.

## Numerical acceptance

DEMO-005: G1 reaches S02 at 15, deployment ends at 30, expires at 150. V02/V04
are available on [30,150): weighted availability 720, weighted downtime 5760,
unweighted availability 240 service-minutes, unweighted downtime 3360, first
restoration 30, final services 0.

DEV-010: first episode stops at 60. G1 was activated at 25 and expires at 145;
the unaffected equipment work remains committed until 145. After fresh approval,
13 weighted services contribute 13*120 and the S01 branch contributes 10*575.
Total weighted availability is 7310; downtime is 23*720-7310 = 9250. End state
has ten available services. This is a fixture calculation, not a commercial or
multi-agent benchmark result.

## Actual verification evidence

- Data check: 201 sizes/SHA-256 values, 31 structures, uncertainty isolation,
  references, 25 districts and the hand-calculated dependency example pass.
- Full final test count is recorded in `docs/ZAHRA_ACCEPTANCE.md`.
- `docs/evaluation/DELIVERY_SMOKE.json`: 31 offline template cases, 25 completed
  incidents and six escalated cases, zero model calls. All three resource-loss
  scenarios reached completion through fresh approval on each episode.
- Browser rehearsal performed on the completion checkout: DEMO-005 approval and
  measured results; DEV-010 pause, accept update, new plan/state, new approval,
  resume and complete. These are local synthetic tests.
- Existing tests verify rejection, stale/source binding, duplicate execution,
  visible-only input loading and non-finite/tampered output rejection. Added
  numerical tests cover horizon events, resumed expiry, partial work, successive
  hidden events, missing approval and unobserved resource-truth isolation.

## Remaining external validation and scope limits

Independent human review of the candidate evaluation set is still PENDING. The
software audit cannot sign off as Kiruthika or another independent reviewer.
Candidates share generator templates; independently vary topology, constraints
and report wording, review labels/outcomes, and version/refreeze a new release
before claiming a validated held-out benchmark. Twenty review entries are supplied
in `docs/evaluation/HUMAN_REVIEW.csv`. Do not tune prompts against these answers
and then call the same cases held out. All evidence here is synthetic; no operator
or commercial deployment is validated.

The incident checkpoint is private in-memory session state. Restarting the app or
losing the session requires starting a new incident; loading history never
restores an approval or silently resumes execution. Cross-process durable resume,
real authentication, dispatch, refuelling and general network topologies are not
part of this MVP. The CP-SAT scheduler retains its five-minute input restrictions;
use the exposed greedy scheduler for supported non-aligned event times. The event
engine integrates integer-minute intervals exactly.

## Tools and attribution

Zahra's existing handoff reported Claude Code with `claude-sonnet-5-5` on Windows;
that is retained as her report, not independently verified model provenance.
The 24 November continuation used ChatGPT/Codex, Python, pytest, Streamlit AppTest,
local browser rehearsal and Git. Runtime OpenAI inference was not exercised.
The exact coding-assistant model identifier was not recorded in the repository.


## Priority 5 — evaluation revision handoff (25 November)

Read [the review instructions](../PRIORITY_5_REVIEW.md). Prepare a new version of
candidate inputs/truth/raw source; preserve the original frozen 201-file release.
Current candidates have 20/20 development topology-descriptor overlap and 34/34
report-text overlap. Diversify topology, routes, resources/windows and natural
wording; manually check the declared labels and expected physical behavior.
The review packet accepts structurally valid unparsed report labels as requiring
human semantic review, not as machine-verified meaning.

A case author or prompt tuner cannot provide its independent sign-off. Route
revisions to Kiruthika or another genuinely independent reviewer, leave declarations
truthful, and create a fresh packet for changed hashes. Co-author credit for this
tooling commit does not certify that review has occurred. No human decisions are
filled by this update. Steps 6–7 are pending.

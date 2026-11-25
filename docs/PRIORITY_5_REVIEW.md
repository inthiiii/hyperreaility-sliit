# Priority 5 — independent evaluation-case review

**25 November 2026 · implementation ready; human decisions pending**

This milestone prepares and enforces the review of twenty evaluation candidates.
It does not run their hosted comparison, sign as a teammate, or certify a held-out
study. Priority 6 (manual application QA/rehearsal) and Priority 7 (final benchmark
and release) remain separate.

## Current findings

The [review packet](evaluation/priority5-20261125/packet.json) audits all twenty
candidates, with two cases in each of the ten intended categories. It retains
input/raw/truth file hashes, declared report labels, evidence sources, resources,
future-event details for evaluators, and expected conservative fixture behavior.
The [case cards](evaluation/priority5-20261125/cards.md) provide a review checklist
for every case; [reviews.csv](evaluation/priority5-20261125/reviews.csv) is the
editable human worksheet. All twenty decisions remain **PENDING**, with reviewer
names and timestamps blank. The original HUMAN_REVIEW.csv and frozen dataset
remain unchanged historical records.

The actual diversity check found:

| Check | Finding |
|---|---:|
| Candidate cases | 20 |
| Distinct topology descriptors | 3 |
| Candidates whose descriptor occurs in development | 20/20 |
| Report texts already present in development | 34/34 |
| Human approvals entered by this update | 0 |
| Inference API calls for Priority 5 | 0 |

Descriptors compare graph depth/branch structure and depot-road layout while
ignoring IDs; they are similarity warnings, not full graph-isomorphism proofs.
Seeded travel, duration and autonomy differences do not by themselves establish
independent scenario diversity. These candidates should be revised before a
strong held-out generalization claim. Accepting a limitation permits a transparently
labelled candidate comparison, not a validated held-out claim.

## Work allocation

**Zahra — prepare revisions and evidence.** Inspect each case's raw, processed and
truth files. Vary topology/upstream dependencies, routes, crew skills/windows,
generator availability/autonomy and report wording in a new dataset version.
Preserve explicit unknowns and evidence authority; check labels and evaluator
outcomes. Record source/tool assistance and revision rationale. A case's author
cannot sign its independent review.

**Kiruthika — independent human check, if she did not author the case or tune the
agent prompts.** Read the case cards, then inspect the source files listed in
packet.json. Check report meaning and every label, resource/timing constraints,
expected escalation or restoration dependencies and diversity. Enter her actual
name/date and decisions after performing that work. A different independent human
must review any cases she authors or any cases for which she tuned prompts.

**Ihthisham — integration and protocol stewardship.** Keep answer files and review
packets out of agent tools/prompts. Preserve dataset versions, retire contaminated
cases, and register the eventual comparison protocol before the later benchmark.
Co-author trailers credit the requested team workstream; they are not review
signatures or evidence that either teammate has completed these checks.

## Checks by category

| Category | Current candidates | What the human must verify |
|---|---|---|
| Equipment only | EVAL-001–002 | Equipment repair semantics, crew skill/time, powered upstream path and unaffected services. |
| Power only | EVAL-003–004 | Generator setup/travel, autonomy/expiry, deployment limit and service dependencies. |
| Power plus backhaul | EVAL-005–006 | Both prerequisites and sequencing; no assertion that power alone repairs a failed link. |
| Skill shortage | EVAL-007–008 | No invented skills/resources; unmet work is recorded without fabricating uncertainty. |
| Route closure | EVAL-009–010 | Closed-road effect and any genuine alternate path; vary the depot-star pattern. |
| Conflicting reports | EVAL-011–012 | Preserve both claims; equally authoritative conflict requires confirmation. |
| Stale reports | EVAL-013–014 | Source authority, observation/receipt times; recency alone never verifies a claim. |
| Missing evidence | EVAL-015–016 | Unknown remains unknown; private truth must not fill the visible gap. |
| Generator exhaustion | EVAL-017–018 | Half-open expiry boundary, full-horizon service accounting and no implicit fuel refill. |
| Resource loss/replanning | EVAL-019–020 | Event-time completed-work retention, unfinished-work pause, current crew window and fresh approval. |

The machine's expected_fixture_behavior is derived from the narrow template
parser/resolver. It is not an independently reasoned gold outcome or optimum.
For natural wording, UNPARSED_HUMAN_REVIEW_REQUIRED explicitly means semantic
verification is still needed. The default release audit remains strict; only the
review-packet path permits structurally valid unparsed labels for human checking.

## Complete the worksheet

For each row:

1. Keep scenario_id and both supplied hashes bound to the exact reviewed files.
2. Enter the actual reviewer name and reviewed_at_utc as an ISO UTC time, such as
   YYYY-MM-DDTHH:MM:SSZ, after the review. A future or timezone-free date is rejected.
3. Set is_case_author, was_prompt_tuner and used_for_tuning to NO only when true.
   YES, UNKNOWN or blanks block release. Reassign conflicted reviewers; retire
   cases used for prompt tuning and replace them in a new version.
4. Mark topology_resources_review, report_semantics_review and
   labels_outcomes_review PASS only after checking them independently.
5. Record diversity_action as REVISED or ACCEPT_LIMITATION, with substantive
   notes explaining the changes or the exact limitation (at least 25 characters).
   ACCEPT_LIMITATION cannot support a stronger held-out claim.
6. Set decision to APPROVED only when ready; otherwise leave PENDING or use
   CHANGES_REQUIRED and explain the problem. No automated process fills approvals.

Self-reported identity/independence cannot be authenticated by this software.
Hashes detect changed files and accidental tampering; they are not digital
signatures or proof of reviewer independence. Follow the declarations honestly.

## Revision and immutable release workflow

Preserve the existing frozen data. For substantive revisions, copy `data/` into a
new directory with the layout `<new-root>/data/`, and make changes in the copied
raw synthetic candidates and matching case index. Regenerate the processed inputs,
truth and manifests in that copied root using scripts.prepare_data.prepare with
its ROOT set to the new root. Never point regeneration at the original frozen
checkout. Keep exactly two candidates per category, with new IDs for replacements.
The packet builder accepts a new root via --root and binds the new file bytes.

The review tool deliberately does not create or revise evaluation answers for the
reviewer. Authors must keep reports/labels/physical truth consistent; the reviewer
must check semantic and numerical outcomes. Any changed input, raw case, truth or
review binding requires a new packet and renewed review. Prior approvals do not
transfer to new hashes. Do not relabel exposed development material as unseen.

From the repository root:

```sh
# Inspect current readiness. Exit 2 is expected while human decisions are pending.
python -m project.evaluation.case_review check \
  --packet docs/evaluation/priority5-20261125

# For revised data: use a new packet directory; preparation refuses overwrites.
python -m project.evaluation.case_review prepare \
  --root /absolute/path/to/new-root \
  --packet /absolute/path/to/new-review-packet

# Only after actual independent human checks and a completely filled worksheet:
python -m project.evaluation.case_review release \
  --root /absolute/path/to/new-root \
  --packet /absolute/path/to/new-review-packet \
  --output /absolute/path/to/review-release.json
```

The immutable release embeds the packet and review rows, with checksums. It is
created only after all twenty exact-hash reviews pass. Missing/duplicate/extra
cases, stale data, missing declarations or incomplete decisions block it. A later
reviewed-candidate run must pass --review-release to project.evaluation.runner;
that gate runs before provider configuration, generation or result-directory
creation, even for template baselines. The benchmark manifest records the release
hash and selected case IDs, not the private answers. This is an enforced workflow
boundary, not an access-control system against someone changing the source code.

The release status is HUMAN_ATTESTATIONS_COMPLETE. It always retains
NOT_ESTABLISHED_BY_SOFTWARE for held-out validity. Statistical validity,
independence, protocol registration and honest claims still need human stewardship.
No completed review release is published by this update.

## Verification and checkpoint status

Full regression: **492 passed in 50.20 seconds**. The actual check CLI exits 2
while review is pending, and a direct candidate-run attempt stops before creating
results or accessing a provider. All 201 frozen dataset file hashes still match.
See [checks.json](evaluation/priority5-20261125/checks.json) for the recorded checks.

See [readiness.json](evaluation/priority5-20261125/readiness.json) for the actual
blocked state and per-case outstanding checks. Tests cover missing/duplicate
reviews, author/tuner/contamination declarations, timestamps, data/packet drift,
release immutability, forged bindings, non-template wording, invalid gold targets,
and the benchmark gate before provider calls. Injected test attestations live
only in temporary test directories and are not genuine human reviews.

Prepared with ChatGPT/Codex assistance in Ihthisham's session. Requested co-author
credit: Zahra Hassan and Kiruthika Vijayakumar. Implementation/review preparation
is delivered; independent human validation remains pending.

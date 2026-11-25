# Priority 5 — requested AI review and frozen revision

**25 November 2026 · revision, AI review, mechanical validation and freeze complete**

The user requested that the coding assistant finish the data revision and review
all twenty cases. That work is delivered as an explicitly AI-authored/self-reviewed
engineering release. It does **not** represent independent human review. No teammate
names, signatures or approval dates were fabricated, and the default human-review
gate remains available and unchanged in meaning.

## Delivered files

| Deliverable | Location | Actual status |
|---|---|---|
| New versioned dataset | [evaluation v2](../releases/evaluation-v2-20261125/README.md) | 20 new EVAL2 case IDs, two per category |
| Filled reviews.csv | [AI review worksheet](../releases/evaluation-v2-20261125/review/reviews.csv) | 20/20 AI_REVIEWED; reviewer_kind AI; independence NO |
| All case checks and numerical reference evidence | [validation.json](../releases/evaluation-v2-20261125/review/validation.json) | 20/20 PASS; 35 declared claims checked |
| Frozen dataset/review manifest | [AI_RELEASE.json](../releases/evaluation-v2-20261125/AI_RELEASE.json) | AI_REVIEWED_FROZEN, 203 file bindings |
| Blank optional human review packet | [human worksheet](../releases/evaluation-v2-20261125/review/human/reviews.csv) | 0/20 human approvals; archival and unchanged |

The original root data, frozen 201-file snapshot and older PENDING worksheets are
preserved. Their pending rows do not describe the completed **AI** review of the
new EVAL2 release. The new release's CSV is the requested filled worksheet.

## What was revised and checked

Twenty distinct backhaul branch/depth descriptors replace the original three.
No v2 descriptor matches development. Roads now include chains, hubs and cross-
links; one closure isolates the affected site, while the other permits an alternate
route. Crew counts, skills, start/end windows and locations vary; generator setup,
autonomy and availability vary under the same one-deployment policy. All 35 report
texts are different from development wording. These are similarity diagnostics,
not evidence of independent authorship or real-world language diversity: the
revision still uses a finite synthetic authoring vocabulary.

All report target/attribute/value labels were checked against the authored wording
and source/time information. Both equally authoritative conflict cases retain
uncertainty; both missing-equipment cases remain unknown. Stale unverified failures
do not override current authoritative healthy reports. Known skill and route
restrictions remain separate from missing evidence.

Independent arithmetic code walks equipment, grid power and every upstream
backhaul link to calculate twenty no-action totals. The separate simulator agrees
on every case. Seven curated one-action fixtures check repair, alternate access,
temporary power and exact expiry. Two crew-loss fixtures verify paused unfinished
work gets no completion credit, prefix full-horizon scores stay null, and stale
approval cannot be reused. These are **mechanism/reference checks**, not hosted
agent benchmarks, optimal plans or independent human gold outcomes. No participant
study, model superiority or financial saving is claimed.

The coding assistant authored and reviewed the cases and previously worked on
runtime prompts. The CSV records author YES and prior tuner YES, with independent
review NO. These cases were not supplied to application agents or used for runtime
prompt tuning in this update. Project inference API calls: **zero**.

## Validation actually completed

- Full repository regression: **508 passed in 53.25 seconds**.
- Focused revision/review/release tests: 58 passed before the full suite.
- Original data manifest/frozen check: all **201** file bindings unchanged.
- New data manifest: **194** operational/generated data files, plus metadata and
  review evidence bound by the **203-file** AI freeze.
- Reproduction test rebuilds the dataset byte-for-byte in a temporary directory.
- Tests reject changed/unlisted data, modified reviews, unsafe snapshot paths,
  false independence claims, label/wording contradictions and stale approvals.
- The deeper graphs exposed a JSON hash bug: integer depth keys >=10 sorted
  differently after serialization. Keys are now strings from construction and
  packets survive JSON round-trips. Original shallow packet hashes stay stable.
- Generation/preparation/download scripts refuse a root with AI_RELEASE.json.
  Both the builder and freeze refuse overwrite operations.

## Inspect the completed review and freeze

```sh
python -m project.evaluation.ai_case_review validate \
  --root releases/evaluation-v2-20261125
```

Expected status: AI_REVIEWED_FROZEN; independent_review false; human_review PENDING.
That distinction is deliberate, not a failed validation.

Reproduction uses a **new empty directory**:

```sh
python -m scripts.build_evaluation_v2 --output /absolute/path/to/new-revision
python -m project.evaluation.ai_case_review review --root /absolute/path/to/new-revision
python -m project.evaluation.ai_case_review freeze --root /absolute/path/to/new-revision
python -m project.evaluation.ai_case_review validate --root /absolute/path/to/new-revision
```

Do not edit a frozen file in place. Prepare another version for future changes.
The optional blank human worksheet is archival inside this frozen snapshot; any
later genuine human review should use a fresh packet outside it.

## Evaluation boundary and next milestones

The default benchmark route still accepts only human-attestation releases. An AI
release requires an explicit **--allow-ai-reviewed** plus its --review-release and
--data-root. The manifest then records AI-assisted synthetic engineering scope,
independence false and human review pending. The flag never establishes held-out
validity or turns an AI row into human approval. It is an explicit alternative
requested by the user, not a silent fallback when human review fails.

The old runtime extraction metric labels exact starter-template phrases. It must
not be presented as natural-language F1 for v2. Label-aware final scoring should
use the reviewed claims in an isolated evaluator at the later benchmark milestone;
never expose the review oracle, private truth, future events or label mapping as
an agent tool. No final benchmark has been run by this update.

The requested software/data revision, AI review and freeze portion of Priority 5
is complete. **Independent human certification remains unperformed.** Priority 6
(application QA/rehearsal) and Priority 7 (final comparison/release) are not started.
Any future study must retain the actual review provenance and limits above.

Prepared with ChatGPT/Codex in Ihthisham's session. Requested co-author credit for
Zahra Hassan and Kiruthika Vijayakumar is separate from case-review signatures.

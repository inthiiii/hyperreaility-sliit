# Evaluation revision v2 — AI reviewed and frozen

The requested revision, AI review of all twenty cases, and mechanical freeze are
complete. This is **AI-authored/self-reviewed synthetic engineering data**, not
independent human validation or a certified held-out dataset.

- [Completed reviews.csv](review/reviews.csv): 20 AI_REVIEWED rows, reviewer
  ChatGPT/Codex in Ihthisham's session; author YES, independence NO, human PENDING.
- [Validation details](review/validation.json): all twenty case checks, declared
  claim semantics and reference arithmetic, including failed-action boundaries.
- [Frozen release](AI_RELEASE.json): exact file sizes/hashes and explicit scope.
- [Review packet](review/packet.json): dataset bindings, labels and resources.
- [Archival blank human worksheet](review/human/reviews.csv): no fabricated signatures.

The v1 candidates EVAL-001–020 are retired for this revision. New IDs are
EVAL2-001–020, two per category. The original repository data and 201-file frozen
snapshot remain unchanged. The v2 release includes byte-identical demo/development
fixtures for provenance comparison; the optional geographic context stays in the
original dataset and is not duplicated here.

## What changed

There are twenty distinct topology descriptors (branch/depth layouts), with zero
matching the starter development descriptors. Road networks include chains,
hubs and cross-links; the two closure cases distinguish isolation from an
alternate route. Crew counts range from two to four, with different skills,
locations and windows. Generator inventory, setup times and autonomy vary under
the existing one-deployment policy. All 35 report texts differ from development
texts and use explicit non-template operational language. Exact-wording overlap
is only a diagnostic: phrases still belong to a synthetic authoring vocabulary,
not real incident language. No real-world generalization claim follows.

## Actual case review

Every declared report target, attribute, value, source/time and resolution was
checked against its authored wording. Conservative resolution keeps both conflict
cases and both missing-equipment cases unresolved; unverified stale failures do
not override authoritative healthy reports. Reference arithmetic independently
walks the powered/equipment/backhaul path. All twenty no-action service totals
agree with the separate simulator. Seven curated single-action checks cover repair,
alternate routing and generator expiry; the two crew-loss cases verify partial
work has no completion credit and prefix full-horizon scores stay null. Reference
approvals are labelled automated fixtures, never actual human decisions.

These are mechanism checks, not optimal schedules or hosted-agent benchmark
outcomes. None of the answers or arithmetic checks were supplied to application
agents or used to tune runtime prompts. Current runtime template-extraction F1
covers only its recognized fixture vocabulary; do not report it as general F1 on
these natural-wording cases. Label-aware final scoring belongs to the later
benchmark milestone and must remain evaluator-only.

| Case | Category | Claims checked | No-action weighted downtime (minutes) | AI review |
|---|---|---:|---:|---|
| EVAL2-001 | equipment_only | 1 | 13680 | PASS |
| EVAL2-002 | equipment_only | 1 | 3600 | PASS |
| EVAL2-003 | power_only | 1 | 5040 | PASS |
| EVAL2-004 | power_only | 1 | 3600 | PASS |
| EVAL2-005 | power_and_backhaul | 3 | 16560 | PASS |
| EVAL2-006 | power_and_backhaul | 3 | 16560 | PASS |
| EVAL2-007 | skill_shortage | 3 | 12960 | PASS |
| EVAL2-008 | skill_shortage | 3 | 14400 | PASS |
| EVAL2-009 | route_closure | 2 | 720 | PASS |
| EVAL2-010 | route_closure | 2 | 3600 | PASS |
| EVAL2-011 | conflicting_reports | 2 | 7920 | PASS |
| EVAL2-012 | conflicting_reports | 2 | 3600 | PASS |
| EVAL2-013 | stale_reports | 2 | 0 | PASS |
| EVAL2-014 | stale_reports | 2 | 0 | PASS |
| EVAL2-015 | missing_critical_evidence | 0 | 15120 | PASS |
| EVAL2-016 | missing_critical_evidence | 1 | 3600 | PASS |
| EVAL2-017 | generator_exhaustion | 1 | 4320 | PASS |
| EVAL2-018 | generator_exhaustion | 1 | 3600 | PASS |
| EVAL2-019 | resource_loss_replanning | 2 | 13680 | PASS |
| EVAL2-020 | resource_loss_replanning | 2 | 14400 | PASS |

## Freeze and later use

The data manifest covers 194 files. The AI release binds 203
dataset/review/provenance files; validation rejects changed or unlisted files.
Preparation, synthetic regeneration and context download guards recognize
AI_RELEASE.json and refuse to mutate a frozen version. The builder also refuses
an existing target directory. Make a new version for any later changes.

```sh
python -m project.evaluation.ai_case_review validate \
  --root releases/evaluation-v2-20261125
```

The default evaluation gate still requires human attestations. For a later
explicitly labelled AI-assisted engineering comparison, supply this version's
`--data-root releases/evaluation-v2-20261125/data`, its `--review-release`, and
`--allow-ai-reviewed`. This flag does not grant independent or held-out status;
that scope is recorded in the experiment manifest. No such comparison is run by
this milestone.

The blank human packet inside the frozen snapshot is archival. To conduct actual
independent review later, prepare a **new packet outside this frozen directory**
using project.evaluation.case_review with --root pointing here. Record a real
reviewer who did not author the cases or tune prompts. A new human release is
separate from this AI self-review record.

The preprocessing quality report records draft status at construction time;
review/reviews.csv and AI_RELEASE.json record the subsequent AI check and freeze.
The same coding assistant authored and reviewed this revision; its prior prompt-
tuning involvement is disclosed. Co-author credit for Zahra and Kiruthika is not
a claim that either person personally performed these reviews. Steps 6–7 have not
been started. No project inference API calls were made.

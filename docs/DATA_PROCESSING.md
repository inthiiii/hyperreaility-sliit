# Dataset inventory and processing procedure

## Inventory
| Material | Included | Purpose | Status |
|---|---|---|---|
| geoBoundaries Sri Lanka ADM2 simplified polygons | Raw GeoJSON, API metadata, attribution file, download provenance | District context layer only | Downloaded public geography; 25 districts; year represented 2017 |
| Western district context | Colombo, Gampaha, Kalutara subset | Optional map framing | Derived from the same public boundaries |
| Operational scenarios | 1 demo + 10 development + 20 evaluation candidates | Exercise recovery decisions | Generated fictional inputs, not downloaded operator records |
| CSV inspection tables | Eight tables per demo/development scenario | Manual review and interface development | Derived from synthetic JSON |
| Evaluation truth and fact labels | Separate directory | Simulator and independent scoring | Unreviewed draft labels; never an agent tool |

No training dataset is necessary for the scoped MVP. Hosted models perform extraction/reasoning, while deterministic tools enforce physical constraints. No fine-tuning is planned.

## Processing steps — Zahra owns the pipeline
1. **Source and provenance:** the downloaded raw public files are already present. Check `data/raw/geoboundaries/metadata.json`, download manifest and attribution. Refresh only if needed using `python3 scripts/download_context.py`. Preserve the actual licence listed by this layer (ODbL 1.0).
2. **Scenario generation:** run `python3 scripts/generate_scenarios.py` only when deliberately rebuilding draft fixtures. Seeds make the fixtures reproducible. Do not run this over a frozen evaluation copy.
3. **Geometry normalization:** `python3 scripts/prepare_data.py` preserves source longitude/latitude, standardizes district properties, checks ID uniqueness, polygon type and broad Sri Lanka coordinate bounds, and produces a three-district subset. It does not perform topological validity checks, derive roads or calculate radio coverage.
4. **Record normalization:** the same command trims report identifiers and whitespace, sorts report receipt/observation times, validates unique report IDs and writes stable JSON/CSV. Boolean `null` means unknown. Do not replace it with `false`, zero, majority guesses or a mean.
5. **Keep evidence:** retain conflicting and stale records with source, observation time and receipt time. Do not drop duplicates simply because they mention the same site. Current draft reports are tiny and templated; enrich wording independently before claiming robustness to real field messages.
6. **Separate answers:** runtime agents load only `data/processed/agent_inputs/<split>/*.json`. Only the simulator/scorer receives `data/evaluation/ground_truth/`. Raw synthetic JSON contains both sides and must never be passed wholesale to agents.
7. **Run checks:** `python3 scripts/check_data.py` checks references, resources, graph connectivity, times, split counts, answer isolation and selected edge cases. Review `data/quality_report.json` and `data/file_manifest.csv`.
8. **Manual review:** Kiruthika opens `data/processed/tables/DEMO-005/` and development CSVs, then fills `docs/manual_qa.csv`. Use `data/evaluation/qa/` as draft expected extraction facts, checking labels rather than assuming they are right.
9. **Independent audit and freeze:** appoint a reviewer who is not tuning agent prompts. They revise candidate cases, vary topology/wording/resources, confirm gold labels and expected behaviour, record hashes, and keep final answer files separate. The current 20 cases do not yet qualify as a credible held-out set.
10. **Integration:** loader validates inputs; evidence resolution creates verified state; planner/validator use that state; simulator uses hidden truth only to measure outcomes. Future events are exposed to the runtime as timestamped reports only when they occur.

## Units and semantics
- Incident time: integer minutes from incident start; stale reports may have negative observation times. Current time may be 5 for the conflicting-report scenario.
- Planning horizon: 720 minutes. Proposed schedule slots: five minutes.
- Work durations: 30–120 minutes; generator deployment 15 minutes. Add travel separately; do not hide it inside work duration.
- Generator autonomy: 120–360 minutes starting when deployment completes. No refuelling, generator pickup or second deployment is in the first scope.
- Roads: fictional undirected depot-star graph; missing direct roads do not mean straight-line travel is possible. Travel between sites uses the depot where necessary. Closed edge means no access on that edge.
- Equipment, upstream connectivity and power are all required for service. Every upstream node/link in the core path matters.
- One service per site is an illustrative dependency, not a population/coverage estimate. Critical weights 5/1 are explicit synthetic policy. Report weighted and unweighted metrics and later sensitivity checks.
- CSV blank boolean cells represent JSON null; lists are JSON strings inside cells. Use JSON as the authoritative runtime format.
- Inputs for future resource-loss events are revealed only at their simulated event time. When a crew becomes unavailable, pause unfinished work and require review.

## Ten draft scenario families
Equipment fault; power outage; combined power/backhaul loss; missing backhaul skill; closed access road; contradictory authoritative reports; stale unverified report; missing critical evidence; generator depletion; resource loss requiring replanning.

These are mechanism tests, not a representative sample of Sri Lankan outages. Candidate tests share a simple topology family with development cases: independent variation is required before formal benchmarking. Missing evidence and impossible repairs must remain visible instead of being converted into invented restored service.

## Evidence access boundary
Keep operational code and evaluator code separate. Agents must not have a general filesystem tool able to read `data/raw/synthetic/` or `data/evaluation/`. Serving only approved scenario objects through an allowlisted loader is stronger than merely telling a prompt not to read answers.

## Source links
- https://www.geoboundaries.org/api/current/gbOpen/LKA/ADM2/
- https://www.geoboundaries.org/api.html
- https://www.openstreetmap.org/copyright
- https://openrouter.ai/docs/api_reference/limits

### Dataset integrity after Git checkout

Processed CSVs use UTF-8 and LF line endings, and `.gitattributes` keeps dataset
line endings stable across checkouts. `python scripts/check_data.py` verifies
that every raw, processed and evaluation file appears exactly once in
`data/file_manifest.csv`, with its actual byte size and SHA-256 checksum.
After intentionally changing datasets, rerun `python scripts/prepare_data.py`
and then `python scripts/check_data.py` before committing the updated manifest.

### Completed loader, audit and release protection (24 November)

The shared typed loader is `project.data.loader.load_case`; it validates filenames,
IDs, references, topology and times using the shared models. Evaluator answers are
loaded separately through `project.data.evaluator.EvaluatorLoader`.
`python -m project.data.audit --output /tmp/new-audit.json` performs a literal-label,
uncertainty and structural audit without inference. The published candidate pack
is frozen by docs/evaluation/FROZEN_DATASET.json; check_data verifies those bytes
as well as the working manifest. Refresh/generation/preparation now refuse to
modify this frozen release in place. Preserve it when preparing a reviewed new
release. Freeze protection is reproducibility, not evidence that the candidates
are independently reviewed or held out. HUMAN_REVIEW.csv remains PENDING.

The older Day 1 scope notes are historical. Independent loader, simulation and
approval-gated continuation are now implemented; see handoffs/zahra.md.

# Dashboard Push 5 — history, exports and evaluator-output views

Date: 24 November 2026. Branch: `feature/dashboard`. Baseline: Push 4 commit `0992df6`.

## Merge scope

The five dashboard milestones can now be merged as an independent UI workstream. The merge includes incident inspection, explicit planning, human review, the simulator boundary, history and result presentation. **It does not establish a complete evaluated MVP:** Zahra's independent simulator/processed-data integration, real measured outcomes, dynamic execution and live hosted-model evaluation remain separate integration work.

## History

History lists saved core runs, operator decisions, simulation attempts and UI setup/workflow attempts. Filters select record type, incident and ID/status search. A saved run opens its schedule, evidence, recorded activity and metadata. Downloads provide filtered summary CSV and selected-record JSON. History also works after scenario files are removed.

History is read-only: no active run/approval is restored, no model is constructed and no simulation is executed. Coordinator statuses describe the recorded run, not current operator authorization. Decision records show actual approval/rejection events separately. Recorded token totals remain unavailable if any request lacks usage; offline zero calls are distinguished from incomplete reporting. No API price is inferred.

Only the exact local-run root and its known `decisions`, `simulation_attempts` and `ui_attempts` subfolders are read. Linked roots/files, malformed data, invalid filenames, mismatched IDs/hashes, non-finite values and oversized files are skipped with safe notices. Core/decision/simulation envelopes are checksum checked; older UI attempt metadata is explicitly unchecksummed. Checksums are not signatures or authentication.

The reader scans up to 1,000 filenames per record kind, considers the latest 200 candidate files by modification time and reads at most 8 MB per file / 32 MB total. This is a bounded window, not a guarantee of complete archival history. Missing related records can therefore reflect the window or an unavailable file.

## Results

Without a matching completed approved simulation, Results shows a pending/empty state. No restoration metrics, improvement percentages or financial savings are generated. With evaluator output, the page presents exact metric keys and values, explicit units if supplied, the trajectory table, completed actions, unmet needs and provenance. Null remains unavailable, not zero. Negative reported values are not silently changed.

An optional line chart uses numeric trajectory fields. The operator selects the evaluator's documented time field and series; units/meanings are not guessed. Missing values remain gaps, and missing/duplicate/non-increasing time is rejected for plotting while the raw table stays visible. The evaluator can provide explicit defaults:

```json
{
  "metric_units": {"actual_metric_key": "actual documented unit"},
  "trajectory_plot": {
    "time_field": "actual_time_key",
    "series": ["actual_numeric_series_key"],
    "time_unit": "actual documented time unit"
  }
}
```

These optional keys belong in SimulationResult.run_metadata. They are presentation metadata, not a replacement simulator schema. Zahra should supply a real example trajectory and exact metric definitions during integration. The chart/table plumbing is tested using explicitly injected test-only outputs; the application attaches no fake simulator or test result.

Current results must match the current plan/state and recorded completed attempt/hash. Historical completed outputs are plotted only when they match a saved run and approval audit, including plan/state/input binding and operator. Incomplete/unlinked records remain inspectable but are not presented as correlated outcomes. Test-only/injected metadata is visibly labelled; interface checks do not establish physical-model accuracy.

## Export and numeric handling

Explicit JSON/CSV downloads filter recognized hidden-truth/future-event fields and credential patterns. CSV downloads neutralize formula-like text in headers/cells; actual numeric negatives are preserved and missing values stay blank. This is not a general privacy anonymizer. Never put hidden evaluator worlds into public result records or send them to agents.

Decision/simulation records now require strict JSON. Simulation values are checked for non-finite numbers in Python form before serialization, because the installed Pydantic version can convert infinities to null in JSON mode. Invalid output fails rather than masquerading as a missing observation.

## Run and verify

```sh
source .venv/bin/activate
python -m pytest -q
python -m streamlit run project/main.py
```

Restart Streamlit after applying. Generate an offline plan and record a decision, then open History. Inspect/download records and return to Planning: the active run and approval must not change. Open Results without an evaluator: expect No simulation results yet, not invented values.

**Actual checks: 161 tests passed**, including **92 UI/service checks**. The 15 new history/result tests cover all record kinds, filters, checksum/tamper failures, symlink/size/count/byte limits, incomplete usage, JSON filtering, CSV formula handling, cross-record joins, current-result identity, null/zero/negative values and units, trajectory mappings/gaps, non-finite output, history without source files, no inference/rehydration and explicit test-output labels.

Browser QA loaded a real offline core run plus recorded approval/rejection events, displayed History and its export controls, and confirmed the Results empty state. No paid API call or independent restoration simulation was performed. Temporary QA records remain ignored and are not part of the patch.

## After merge

Connect Zahra's approved loader and independent evaluator through the existing callback adapter, verify actual metrics/trajectory semantics, and run end-to-end tests. Add authentication only if deployment scope needs it. Finish dynamic execution/replanning, held-out hosted comparisons and final documentation/demo. See `docs/DASHBOARD_MERGE_CHECKLIST.md` for the concrete merge scope and follow-up list.

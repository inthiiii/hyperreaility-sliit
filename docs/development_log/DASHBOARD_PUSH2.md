# Dashboard Push 2 — incident inspection

Date: 23 November 2026. Branch: `feature/dashboard`. Baseline: pushed foundation `e6b34e1`.

## What changed

The Incident page now has four tabs:

| Tab | Available behavior |
| --- | --- |
| Network | Parent-to-child backhaul diagram, optional undirected roads, local status/unknown indicators, critical-service marker, site selector and dependency chain, plus equivalent site/link/road tables |
| Evidence | Report ID, source and source class, observed/received incident minutes, age, receipt lag and raw text; source/search filters and a full report inspector |
| Resources | Crew locations, skills and recorded time-window status; generator inventory, location, autonomy/deployment duration; permitted action catalogue |
| Service priorities | Fixed policy weights, critical/standard associations, policy evidence, critical-only filter, recorded approval flag and evidence/crew-loss rules |

Counts and views are read-only projections of validated visible inputs. They do not invoke the resolver, scheduler, coordinator, hosted models or simulator. All report/source labels are preserved. A recognized source does not verify a statement's interpretation; equally authoritative contradictions still need the later reconciliation workflow.

## Interpreting the diagram

The layout is computed from the dependency tree, not geographic coordinates. It handles the collinear synthetic positions in DEMO-005 without drawing overlapping straight links. The core is a reference node, not a separately observed healthy asset; the depot position is a schematic anchor. Directed arrows show parent-to-child backhaul. Optional dotted road lines are undirected; they do not depict a selected crew route or travel distance.

Green/check: local equipment and grid observations are OK. Coral/exclamation: a known local fault. Amber/question: unknown. A gold outer ring identifies a critical-service association. These local flags do not establish end-to-end connectivity, coverage or restoration. Use the image's fullscreen control and the equivalent tables for small labels.

In DEMO-005 the diagram correctly retains three unknown snapshot fields: S01 grid, S02 grid and L01 backhaul. Reports describe failures, but Push 2 does not silently reconcile those reports. The snapshot shows zero known local-site and link faults, three unknowns and one critical service; this is not a claim that the network works.

## State and resource rules

Incident filters reset on input content changes. Changing a view/filter does not change core session state or create a plan. Switching scenarios retains the foundation's plan/approval/result invalidation. Report text renders as text, not HTML. SVG labels are escaped and the diagram is displayed through Streamlit's image renderer with alternative text. The initial inline-HTML approach was rejected by visual testing because sanitization removed the SVG; it was replaced before delivery.

A crew is in its recorded window for start ≤ now < end. This is not an idle/busy or reachability assessment. Generator availability is an inventory flag, not an allocation. Autonomy begins after deployment completes. Catalogue work durations exclude travel. Policy weights are displayed without editing. Counts refer to synthetic service associations, not customers or measured availability.

## Verify

```sh
source .venv/bin/activate
python -m pytest tests/ui -q
python -m pytest -q
python -m streamlit run project/main.py
```

Recorded results: **27 UI tests passed; 96 tests passed overall** on the existing environment. New checks cover tri-state snapshots versus raw reports, upstream/local distinction, window boundaries, source/search filters, fixed weights, diagram edges/arrows and optional road layer, critical markers, escaped labels, every development fixture, image-renderer presence, zero-inference browsing, filter reset and empty inventories/unapproved policy.

Browser verification on the final build confirmed the loaded SVG image, report search showing one of three reports with REP-002 selected, and Resources/Service priorities tabs. Desktop widths were checked; temporary viewport overrides were reset. No live model, restoration simulation or performance claim was tested.

## Push and PR workflow

Apply on `feature/dashboard`, run tests, review the staged files, then commit and push to the same branch. An existing PR from this branch updates automatically. Keep it open for Pushes 3–5 rather than merging an incomplete workflow. Do not force-push or modify main. If a teammate has already merged the dashboard PR, inspect the branch/base before proceeding.

## Remaining integration

Push 3 connects explicit planning actions and displays actual evidence extraction, schedule and validation. Push 4 connects recorded operator decisions and the simulator boundary. Push 5 connects independently measured outcomes and run history. Zahra's loader and evaluator remain separate; no hidden truth, preprocessing or core implementation was changed in Push 2. No new package dependency or external diagram service is required.

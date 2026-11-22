# Ihthisham core implementation

Date: 22 November 2026. Source baseline: setup merge a2f7bee. Work implemented in the isolated `relink-core` checkout on `feature/core-planner`; user checkout retains its original working tree.

## Files

Core: schemas, state resolver, validator, greedy/CP-SAT planner, coordinator/approval and demo runner. Hosted adapter: project/llm/client.py. Offline fixture parser: project/agents/extraction.py. Tests and visible development fixtures: tests/core. Interfaces and limitations: docs/DATA_CONTRACT.md and docs/CORE_IMPLEMENTATION.md.

## Actual verification

Python 3.11.18, using the existing project environment (Pydantic 2.14.4, OR-Tools 9.15.6755, NetworkX 3.6.1, OpenAI SDK 3.57.0). Final core suite: 49 tests passed in 4.94 seconds. All 31 starter input JSON files passed schema compatibility checks. Additional 16 to 19 site static scenarios produced valid schedules under independent checking; solver status was OPTIMAL for these development examples. No hosted API call or spend. SDK request parameter presence checked locally. Template demo produced an awaiting-approval plan, one S02 generator deployment and zero model calls. Predictions match the hand-calculated static example; no independent simulation or benchmark was run.

## Reproduce

```sh
source .venv/bin/activate
python -m pytest tests/core -q
python -m project.core.demo --scenario tests/core/fixtures/DEMO-005.json --mode template --output /tmp/relink-core-demo.json
```

## Next integrations

Publish the shared models first. Zahra imports ScenarioInput/SimulationResult and supplies evaluator isolation, event execution and metrics. Eyaas imports Coordinator, approve and check_approval. Operator-confirmation reports must be recorded before evidence is resolved; clients must rebuild a new state version after material changes. Never mutate an approved object in place expecting its approval to survive.

Required follow-up: persistent traces, authenticated operator identity, full future-event lifecycle and independent evaluation. Exact model ID is intentionally unset until the user selects/tests a hosted model. Some transport environments may require optional SOCKS dependencies; no live provider transport was validated here.

## AI disclosure

Source and tests were created with ChatGPT/Codex assistance. Fixture parser is deterministic and narrowly scoped. Fake adapter responses verify orchestration only. Do not count them as real model results or claim four-agent superiority without the planned paired evaluation.

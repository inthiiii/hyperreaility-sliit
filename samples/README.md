# Input and output samples

A small, readable set of real inputs and outputs from the submitted system. Nothing here was edited by hand. Every output file is copied byte-for-byte from the frozen held-out benchmark run [`results/final/evaluation-v3-run1`](../results/final/evaluation-v3-run1/README.md), except the plan summary PDF, which was generated from those files by the app's own export code (`project/ui/plan_export.py`).

## Inputs (`input/`)

| File | What it is |
|---|---|
| [`DEMO-005.json`](input/DEMO-005.json) | The demo incident used in the video and the user scenarios: 5 sites, 2 crews, 1 generator, 6 reports. Also a valid template for **+ Add an incident (JSON)** in the app (change `scenario_id` first). |
| [`EVAL2-001.json`](input/EVAL2-001.json) | One of the 20 frozen held-out incidents: 15–20 sites, mixed-source reports (NMS alarms, field messages, road bulletins, duty notes) and distractors. |

Both follow the `ScenarioInput` contract ([DATA_CONTRACT.md](../docs/DATA_CONTRACT.md)). They contain **only what the agents may see**. Hidden truth and labels live separately under `releases/evidence-v3-20261126/data/evaluation/` and are read only by the simulator and scorer.

## Outputs (`output/EVAL2-001/`)

The same incident planned three ways (repeat 0 of 3 for each), then measured by the same independent simulator:

| Variant | Plan trace | Simulator result | Weighted downtime | Model calls |
|---|---|---|---:|---:|
| CP-SAT without AI (`optimizer`) | [`optimizer_run_episode0.json`](output/EVAL2-001/optimizer_run_episode0.json) | [`optimizer_simulation_episode0.json`](output/EVAL2-001/optimizer_simulation_episode0.json) | 13,680 | 0 |
| Single agent (`single`) | [`single_run_episode0.json`](output/EVAL2-001/single_run_episode0.json) | [`single_simulation_episode0.json`](output/EVAL2-001/single_simulation_episode0.json) | 1,235 | 2 |
| Multi-agent (`multi`) | [`multi_run_episode0.json`](output/EVAL2-001/multi_run_episode0.json) | [`multi_simulation_episode0.json`](output/EVAL2-001/multi_simulation_episode0.json) | 1,235 | 6 |

- **Plan trace** (`*_run_episode0.json`): the full run record, checksummed. `payload.messages` is the agent-to-agent conversation (sender, recipient, state version, typed finding); `payload.plan` is the schedule; `payload.validation` is the independent validator's verdict; `payload.model_usage` lists every model call with tokens, latency and request IDs.
- **Simulator result** (`*_simulation_episode0.json`): the approval record (automated benchmark operator, not a human) and the measured outcome: service availability intervals, completed actions, unmet needs and metrics.
- [`attempts_summary.json`](output/EVAL2-001/attempts_summary.json): the three benchmark rows for this case (status, calls, tokens, time, measured downtime).
- [`multi_plan_summary.pdf`](output/EVAL2-001/multi_plan_summary.pdf): the one-page plan summary the app exports (crew jobs, agent reasons, approval, measured result, no-AI comparison).

**What the sample shows:** CP-SAT alone cannot read the reports, so it leaves the faulty assets it cannot confirm unrepaired (13,680 weighted service-minutes down). Both AI variants extract the faults from the reports and cut downtime by 91 % to 1,235. On this case single and multi agent reach the same result, which matches the overall benchmark (no significant multi vs single difference).

## Reproduce

```bash
python -m project.evaluation.runner \
  --scenarios releases/evidence-v3-20261126/data/processed/agent_inputs/candidate_evaluation/EVAL2-001.json \
  --data-root releases/evidence-v3-20261126/data \
  --variants optimizer single multi --repeats 1 --allow-live \
  --freeze releases/evidence-v3-20261126/FREEZE.json --output results/local_benchmarks/sample
```

Held-out cases only run with `--freeze`, which re-checks the model, settings, prompts and data hashes recorded before the benchmark and stops on any drift. The `optimizer` variant runs offline. `single` and `multi` need `OPENAI_API_KEY` in `.env` and cost about USD 0.03–0.04 per run. Hosted model outputs can differ between runs; the frozen run above is the reported evidence.

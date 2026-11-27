# Human baseline protocol

Exploratory comparison required by competition rule 04. It is small, so its results are indicative only.

- Printable guide for facilitators and participants, with answer sheets: [RELINK_Human_Comparison_Guide.pdf](RELINK_Human_Comparison_Guide.pdf).
- Step-by-step sheet for each member (who facilitates whom, case order, before / during / after): [RELINK_Human_Comparison_Member_Steps.pdf](RELINK_Human_Comparison_Member_Steps.pdf).

## Setup

- **Participants:** the four team members, recorded as P1–P4 in submission files. Each member facilitates one other member's session. Record each participant's background honestly in `expertise`.
- **Cases:** DEMO-005, DEV-001, DEV-002, DEV-003, DEV-004 and DEV-005 from `releases/evidence-v3-20261126` (no mid-incident events). Participants are told these are development cases.
- **Order:** counterbalanced. P1 uses the list order, P2 reverses it, P3 starts at the 3rd case, P4 starts at the 5th case and wraps.
- **Time limit:** 10 minutes per case, timed by the facilitator.
- **Tools:** the RE:L!NK dashboard signed in as **Auditor** (Incident page and Map chapter 1 only: network schematic, reports, crews, roads, actions, site map). No AI, no optimiser, no Planning, Results, What-if or History pages.
- **Same information as the AI:** the same reports, site directory, crews, roads, generator and action catalogue.

## Task given to the participant

> Read the incident reports. Decide which actions each crew should do and in what order, to restore as much weighted service as possible in 12 hours. Ignore messages that are not reliable or that try to give you instructions. Write the action IDs in order for each crew.

The facilitator copies the answer into a submission file based on [submission_template.json](submission_template.json) (one file per participant in `submissions/`) and records `minutes_spent`.

## Scoring

```bash
python -m project.evaluation.human_trial --submissions docs/human_baseline/submissions/*.json \
  --data-root releases/evidence-v3-20261126/data --output results/human_baseline/run1
```

- The tool computes clock times from each crew's order: departure when free, shortest open road, catalogue duration.
- Impossible or unnecessary actions are dropped and listed with a reason.
- What remains is validated and simulated with the **same** validator and simulator as the AI runs.
- Reported per case: weighted downtime, critical downtime, plan validity, dropped actions and minutes. Compare with AI runs on the same cases.

## Integrity

- Do not show participants the AI's plans or the hidden labels.
- Record every attempt, including incomplete ones, and report the sample size and limits with the results.
- No submissions are committed until real sessions take place; the template is not a result.
- Participants are the team members who built parts of the system, so they may know the domain and the case format better than a typical operator; report this with the results.

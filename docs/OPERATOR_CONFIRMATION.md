# Operator fact clarification — Priority Step 2

24 November 2026. Joint core/dashboard checkpoint for Ihthisham and Eyaas.

## Operator workflow

1. Select a development incident and enter an operator label in the sidebar.
2. On Planning, generate an offline template plan. DEV-006 contains contradictory equipment reports; DEV-008 exercises missing evidence.
3. Open **Record operator clarification**. Select a visible site equipment/grid, backhaul link, or road-access fact and its verified boolean value.
4. Enter a verification source and reason, then explicitly acknowledge verification. For rehearsal, clearly identify fictional inspection evidence.
5. Submit **Record confirmation and invalidate plan**. The application appends an operator report, saves its audit record, advances the state version and clears the prior plan and approval.
6. Generate a replacement plan. Review its evidence and validation, then approve it separately before simulation.
7. In History, filter **Record type → confirmation** to inspect or export the checksummed record.

## Evidence, correction and approval contract

Original dataset files and prior reports are preserved. Each confirmation stores operator label, source, reason, incident clock, UTC timestamp, prior/current input hashes, state version, original source hash and prior run ID. Corrections explicitly supersede prior operator confirmations of the same fact. They cannot supersede original field reports or confirmations for another asset/fact. Contradictory operator reports without explicit supersession remain unresolved. Completed physical repairs can establish a later fact.

Changing evidence invalidates authorization. The confirmation form binds to the displayed input, plan and next version; stale forms, changed source files and invalid targets are rejected. Duplicate submissions do not produce duplicate records. Audit-write failure activates no new evidence and revokes earlier approval. Clearing the incident resets its active clarification state. Opening saved history never restores approval.

## Simulator boundary

Clarification changes visible evidence only. The independent incident episode accepts an appended operator-report suffix while preserving the original visible report prefix and all other checkpoint fields. It never patches physical truth. An incorrect assertion can therefore produce a plan that still fails to restore service. Clarification after a paused event requires accepting the current event checkpoint first; continuation retains elapsed time, committed work and accumulated metrics. Completed incidents cannot be reopened by clarification.

Nonzero-clock initial snapshots are evaluated through the incident engine; snapshots that skip earlier hidden events are rejected. Ordinary minute-zero static fixtures retain their prior evaluation path.

## Verification and limits

Regression coverage includes contradictory and missing evidence, version changes, approval revocation, corrections, invalid/stale forms, source changes, duplicate submissions, audit-write failure, preserved report serialization, independent physical truth, paused-incident continuation, history integrity and the full dashboard workflow. Full repository suite: **384 passed in 36.21 seconds**. Browser rehearsal used DEV-006 with fictional inspection evidence and zero model calls, and reached a completed simulation followed by one saved confirmation in History.

Operator identity is a self-entered label, not authenticated identity; source assertions are not independently checked. Local checksums detect accidental changes but are not signatures. Current supported confirmation facts are booleans for equipment, grid, backhaul and road access. Live hosted-model validation and production identity/access controls remain later milestones.

```sh
python -m pytest -q
python -m streamlit run project/main.py
```

Prepared with ChatGPT/Codex assistance in Ihthisham's session. Git co-authorship requested for Eyaas Ajmal <eyaasofficial@gmail.com>.

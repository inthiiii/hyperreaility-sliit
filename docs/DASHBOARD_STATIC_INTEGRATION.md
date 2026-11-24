# Independent simulator integration (supersedes the static-only checkpoint)

The original static adapter is now the event-capable adapter in `project/ui/backend.py`.
It attaches a private IncidentEpisode to each selected CoreSession, imports no
mock backend, and reads evaluator truth only after explicit approval. The source
file remains bound throughout continuation; a material disk change invalidates
execution. Missing backend imports still leave the browsing/planning UI usable.

`project.ui.continuation.accept_checkpoint` accepts only a matching recorded paused
result and its live safe checkpoint. It clears prior active authorization without
resetting the incident or state-version counter. The operator generates a new plan
and approves it; the same evaluator retains previous service intervals and fuel.
Projected resource reservations and committed earlier work are shown on Planning.

Earlier temporary blocks for dynamic cases and exact-horizon events have been
replaced by tested engine behavior. Prefix output has null full-horizon metrics;
completed output covers minute 0 through 720 without double counting. Event
ordering and the conservative no-partial-credit policy are in handoffs/zahra.md.

Run `python -m pytest tests/ui/test_static_integration.py tests/ui/test_dynamic_integration.py -q`.
Use DEMO-005 for static recovery and DEV-010 for event/accept/replan/reapprove/resume.
No local LLM or live API call is required. See ZAHRA_ACCEPTANCE.md for evidence and
remaining independent human evaluation review. Durable resume after app restart
and production authentication remain outside the MVP.

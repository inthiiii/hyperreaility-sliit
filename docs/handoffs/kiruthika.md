# Kiruthika — Priority 5 independent review handoff

Read [PRIORITY_5_REVIEW.md](../PRIORITY_5_REVIEW.md), then the
[twenty case cards](../evaluation/priority5-20261125/cards.md) and
[human worksheet](../evaluation/priority5-20261125/reviews.csv).

1. Confirm you did not author the case, tune its agent prompts, or use it for tuning.
   Otherwise assign that case to a different independent reviewer.
2. Inspect the raw/input/truth files referenced in packet.json. Check topology,
   resources/windows, report meaning/authority/timing, every declared label,
   missing evidence, event behavior and service accounting.
3. Ask Zahra for a revised dataset version where needed; a changed input/truth/raw
   hash invalidates prior review. Current template overlap is substantial.
4. Enter your actual name and UTC date only after performing the checks. Complete
   PASS/NO declarations truthfully; record revisions/limitations and rationale.
   Keep PENDING or CHANGES_REQUIRED for unresolved cases.
5. Run the check command from the instructions. Release remains blocked until all
   twenty rows meet the gate. The release is a record of human declarations, not
   software proof of independent or held-out validity.

This handoff contains no completed human review. Requested co-author credit is
separate from review sign-off. Prepared with ChatGPT/Codex in Ihthisham's session.
Priority 6–7 are not started by this update.


## Priority 5 — AI-authored/reviewed v2 completion

The user requested the coding assistant perform the revision and review. See
[the completion record](../PRIORITY_5_AI_COMPLETION.md): twenty new cases,
twenty completed AI review rows, checked physical/label mechanisms and a frozen
203-file release. No human signature was entered on your behalf. Independent
human validation is still unperformed; co-author credit is separate. The original
frozen data and blank human worksheet are preserved. Full regression: 508 passed;
zero project inference API calls. Steps 6–7 remain pending.

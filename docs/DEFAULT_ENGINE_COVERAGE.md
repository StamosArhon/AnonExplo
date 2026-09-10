# Default-engine destination coverage (2026-09-10)

Approved scope: four fresh public EN/EL destination fixtures through the unchanged
browser-default route, metrics only. Freeze fixtures in Git before any query.
Use test-browser-search.ps1 -Suite default-audit -PauseSeconds 20 once after VPN
preflight. No engine override, category/time filter, cookies, snippets or result
page fetches. Existing production processor cooldowns apply. Stop on first
degradation; no retries, automatic suffix resume, cache reset or VPN rotation.

Predeclared measure: expected official domain within the top five, reciprocal
rank, latency, errors and same-response top-five engine credits. Host match is
destination coverage only: it cannot establish that the exact requested page is
useful, correct or in the requested language. Shared credit is counted once per
engine per merged result; sole credit is not an engine-removal counterfactual.
Do not infer marginal relevance or change weights from these counts.

All four passing with no errors would support current destination coverage, not
general search superiority. Missing hosts identify follow-up cases, not a reason
to retry immediately or enable new providers. Once evaluated, fixtures become
regression evidence, not unseen holdouts. Production remains unchanged.

Outcome and validation: pending.

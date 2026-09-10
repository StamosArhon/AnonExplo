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

## Completed outcome

Fixtures/tooling frozen and pushed at 46b0a8e before first evaluation. VPN and
gateway-binding preflight passed. One run, unchanged browser-default selection:
Brave, Yahoo, Bing and Wikipedia eligible; three web engines returned rows on
every sample. No errors, retries, suffix runs or fetched result pages.

| Fixture | Rows | Expected domain rank | Seconds | Top-five credits (sole) |
| --- | ---: | ---: | ---: | --- |
| default-pathlib | 34 | 1 | 1.17 | Brave 5 (3), Yahoo 2 (0) |
| default-css-grid | 34 | 1 | 0.93 | Brave 4 (2), Yahoo 3 (1) |
| default-library-el | 33 | 1 | 1.26 | Brave 2 (2), Yahoo 2 (2), Bing 1 (1) |
| default-cadastre-el | 36 | 1 | 1.17 | Brave 5 (4), Yahoo 1 (0) |

Four of four expected domains rank first; mean response 1.13s, reciprocal rank
1.0. Across 20 top-five positions: Brave credited on 16 (11 sole), Yahoo on 8
(3 sole), Bing on 1 (1 sole). Credits overlap and do not sum to 20. Wikipedia
produced no standard result rows in these metrics; infoboxes are not counted.
No conclusion about its overall usefulness follows from that absence.

Decision: retain all current defaults and Bing weight 0.35. This sample supports
healthy official-destination coverage, not general relevance or speed gains.
The fixtures are now observed regression evidence; do not rerun as fresh holdouts.
Next meaningful relevance assessment would require separately approved bounded
snippet grading of fresh informational questions, with frozen rubrics. Do not
replace that assessment with more domain-hit tests or infer quality from credits.

Full validate.ps1 passed: 70 host + 12 historical News + 11 timeout semantics +
13 date tests (106 Python executions), 20 negative Compose cases, seven negative
identity cases plus equality, isolated managed build with production tag unchanged,
native settings/privacy/ranking, blocked direct egress and outage/recovery cleanup.
Optional DDG web/client candidate suites were not repeated (unchanged/unrelated).
Production settings, image, VPN, browser profiles and services were not modified.
No installer or deployment applies; reviewed tooling/report follow normal Git
commit/push, main merge and scoped local/remote branch cleanup.

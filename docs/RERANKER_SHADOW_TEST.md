# Bounded local shadow test

User-approved scope: six fixed public Greek/English fixtures, single retrieval
per case, no search or browser configuration changes. Four reporting cases and
two unrelated-topic controls. Freeze fixtures and policy before first query.
This is a small exploratory evaluation, not a general relevance benchmark.

Use the already provisioned hash-checked model and exact existing CPU image.
Disposable non-root network-none container, read-only model/scripts, no ports,
no credentials, no logs, no result files. Host sends bounded title/snippet pairs
over stdin and gets only numbers back; local private domain list stays on host
in ignored data/preferences. No pages fetched, history accessed, new provider,
remote inference, query expansion, dependency download or production service.
Approved bounded public snippets may be displayed for grading, never saved as
files or committed. Memory/swap and tool conversation are not secure-erasure guarantees.

Live preflight verifies production VPN and default General recipients. One-shot
marker, 20-second pacing, stop on first upstream error/empty response or local
failure; no retry or suffix resume. Rerank at most first 24 rows from the same
response; unscored tail is unchanged. Existing gate remains frozen: score >=.8,
native-score boost 15%, maximum two positions, cannot pass a result with model
relevance more than .05 higher. Missing/invalid native scores retain order.
Model sigmoid is not a calibrated probability and cannot judge factual truth.

Record per-case numeric grades: 0 irrelevant, 1 partial, 2 directly useful for
the fixture rubric. Compare native/shadow top-five mean grade / 2, inspect every
preferred candidate and every promotion. Record coverage, latency and errors.
Do not recommend integration if an irrelevant preferred result is promoted or
top-five utility decreases. No observed promotions means benefit unproven, not
success. Target <=2 seconds warm model overhead; no threshold tuning on these
observations. Once observed these are regression fixtures, not fresh holdouts.

## Execution and decision (2026-09-11)

Fixtures/policy frozen and pushed at d2fea33. An initial preflight harness import
error was fixed at e0489ee before any search or model container; the attempted
marker had not been created. No fixture or policy changed.

Second preflight passed: three healthy production services, correct image,
VPN-shared namespace and DNS, working HTTPS, distinct search/host egress,
expected General recipients, all seven model artifacts verified. Exact existing
CPU image started with network=none. Model load took 5.793 seconds and a single
public warm-up pair succeeded. This is startup latency, not real-result inference.

The first fixture (shadow-el-surveillance) returned 17 partial rows and a Brave
error classified as `other` (not established as a rate limit, timeout or CAPTCHA).
The test stopped immediately, before scoring or displaying any real result.
Remaining five fixtures were not sent. No retry, VPN rotation, cooldown reset,
configuration change or production integration. Disposable worker removed.

Outcome: **inconclusive; do not integrate**. Zero healthy query comparisons,
zero real-result grades, no measured relevance benefit or real-snippet latency.
The earlier synthetic trial remains valid only within its original limits.
The first fixture is attempted, the other five remain unobserved; do not resume
this batch or call it six successful searches. Live entrypoint is now retired
and the one-attempt marker retained. Private source preferences remain local
and ignored, not installed in browser search.

Validation: validate.ps1 passed 94 host tests, 12 historical candidate tests,
11 timeout tests, 20 negative Compose cases, identity checks and isolated repair
image build without changing the production tag. Full runtime validation could
not start: Docker automatic address pools are fully subnetted. No unrelated
networks were removed. Post-retirement host tests and refusal check are run
separately. The branch is not fully validated and must remain unmerged pending
resolution of that independent infrastructure blocker. No release applies.

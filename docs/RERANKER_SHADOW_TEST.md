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

Execution/results: pending. Production integration is outside this test scope.

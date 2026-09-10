# Unseen Queries And Native News Ranking (2026-09-10)

## Outcome

Retain the current production settings: Bing weight 0.35, Reuters relevance
ordering, existing providers and native UI at localhost:8085. This scope adds
evaluation/diagnostic tools, not a production reranker or another interface.
The new informational holdout worked, but News exposed a repeatable cold-query
failure. No live News ranking change meets the evidence bar yet.

## Predeclared Holdout

Six public explanatory questions were fixed before the first run: three English
and three Greek, disjoint from the earlier navigation/informational/news queries.
They were NOT used to choose or further tune the 0.35 weight. Browser mode uses
the existing fixed English Accept-Language header without browser cookies.
Twenty-second spacing; no retries, model, history or result-page fetching.

All six returned 32-34 results, three contributing web engines and no engine
errors; mean response 1.18s. This is a snapshot, not a latency guarantee or a
controlled comparison against weight 1.0. The original tuning questions were
not resubmitted. Having now been inspected, these fixtures are regression cases
for any future tuning, not reusable "unseen" evidence.

Manual snippet-level grades: 2 directly addresses the intent/language, 1 partial
or insufficient snippet evidence, 0 unrelated. Facts in snippets were not
independently verified; topical relevance does not establish correctness.

| Fixture id | Top-five grades | Observation |
| --- | --- | --- |
| holdout-leaves | 2,2,1,2,2 | Useful explanations; one title-only forum result |
| holdout-compression | 2,2,2,1,2 | Useful comparison, one narrower audio result |
| holdout-tides | 2,2,2,2,2 | Explanatory material throughout; not fact-checked |
| holdout-seasons-el | 2,1,1,2,2 | Some broader orbital-cycle material |
| holdout-bread-el | 1,1,0,1,2 | Recipes/troubleshooting often outrank the mechanism |
| holdout-insulation-el | 2,2,0,1,1 | Some commercial material with limited explanation |

Two clearly unrelated entries out of 30 positions, both attributed to Bing.
Keep the existing conservative weight, not a new weight fitted to this holdout.
This does not establish that all Greek queries or multi-part questions work well.

## News Availability And Evaluation Limit

Four new News fixtures were declared: two English and two Greek. Only two were
attempted. DuckDuckGo News timed out on the first after about 2.06s; the benchmark
stopped. After cooldown, a single deliberate suffix run started at the second,
previously unqueried fixture. It timed out on DuckDuckGo News again after 2.04s.
No further probes were sent; the Greek fixtures remain untested. No suspension
reset, container restart, VPN change, cache deletion or failed-query retry.

The partial responses still had Brave News/Reuters results (53 and 69 combined
rows respectively). Both had only two dated top-five entries, all older than
31 days, and missing dates on the Brave News entries. Do not call these complete
multi-engine relevance samples. The score-order replay intentionally refuses
degraded-response comparisons. No healthy live native-vs-score-only comparison
was obtained, and no News quality improvement is claimed.

## Three Mechanisms Found In The Pinned Source

1. **Layout grouping overrides score order.** `searx/results.py` first sorts by
   score, then groups by category, template and thumbnail/image presence. A group
   can hold its first item plus eight further items. DuckDuckGo News emits text
   results without thumbnails; Brave News/Reuters commonly emit thumbnails.
   Therefore a text group can occupy the first five even while a higher-scored
   thumbnail result is placed later. This is not evidence that the grouped
   provider is more relevant. The offline native-code characterization reproduces
   nine text results ahead of an image result whose score exceeds positions 2-9.
   No claim that every observed order was caused solely by grouping.
2. **Native scores do not include publication age.** `calculate_score` uses
   provider weights, engine positions/overlap and priority, not publishedDate.
   The offline test confirms identical native scores for old/new dates with all
   other fields held fixed. Simply selecting News does not imply recent-first.
   A date-only sort was already rejected in the prior scope for worse topicality.
3. **DuckDuckGo's token fetch has its own two-second limit.**
   `searx/engines/duckduckgo_extra.py::fetch_vqd` explicitly calls `get(timeout=2)`
   before the actual news request. The configured six-second engine timeout
   does not replace that inner limit. The observed durations strongly fit this
   path, but no live HTTP trace was captured to prove the failing request stage.
   `duckduckgo.py` can reuse a query/UA-specific token for an hour. Older fixtures
   can therefore exercise a warm-cache path that unseen queries do not. Cache
   contents were NOT inspected, so warm-vs-cold status is inferred, not measured.

The local token cache uses a secret-hashed query/UA key and a token value, with a
one-hour configured expiry. It is operational cache data, not a plaintext search
history; expiration is not a secure-erasure guarantee. It is local and was
already present. No new cache, query database or retention policy was introduced.

## Repeatable Tools

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite holdout -ReviewTop5 -PauseSeconds 20
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite news-holdout -ReviewTop5 -CompareScoreOrder -PauseSeconds 20
# Manual selection only, after diagnosing degradation; never automatic resume:
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite news-holdout -StartAt 3 -CompareScoreOrder
```

These commands are examples, not instructions to retry the failed provider now.
`CompareScoreOrder` sorts the same in-memory response by native numeric scores:
no added searches, persistence, result deletion or production change. Equal-score
ties preserve returned order; original pre-grouping tie order cannot be recovered.
Missing/nonfinite scores are rejected, never invented. Aggregate metrics report
changed top-five membership, score inversions and per-engine date availability.
Optional review displays at most five native and five candidate titles/snippets.
Default output remains content-free metrics. Treat review text as untrusted.

`check-native-ranking.py` exercises the installed ResultContainer and scoring
code inside isolated validation. Only uninitialized metric counters are stubbed;
ranking, normalization and merging are real. It sends no requests. Assertions
characterize this pinned version; review them on an image update rather than
blindly preserving upstream bugs. Initial run failed on uninitialized metrics;
the harness was corrected, not the SearXNG algorithm.

Final validation passed 32 benchmark unit tests, 14 negative Compose policy
tests, generated-startup checks, this native ranking characterization and
offline UI/privacy/egress/recovery checks. Live ops passed with three healthy
services and unchanged VPN-only search routing. Custom image builds are not
applicable (no build contexts). No live ranking deployment or restart occurred.

## Next Decision

Prepare a separately scoped, reversible adapter/ranking patch experiment, first
in an isolated candidate sharing only the existing VPN namespace. Investigate
the two-second token acquisition budget and compare score ordering without
layout grouping, while preserving native UI, thumbnails proxying, all explicit
filters, cooldowns and provider recipients. No production monkeypatch/fork is
introduced here. Do not add a language model to compensate for unavailable
engines or metadata gaps. Require fresh public fixtures, bounded traffic and
topicality/freshness review before shipping any candidate.

## Source Provenance

Read directly from the deployed digest-pinned SearXNG image:
`searx/results.py`, `searx/engines/duckduckgo_extra.py`,
`searx/engines/duckduckgo.py`, `searx/engines/brave.py`, and plugin hooks.
No settings-only switch to bypass the hard-coded grouping was found in that
implementation. [Result fields](https://docs.searxng.org/dev/result_types/main/mainresult.html)
and [UI settings](https://docs.searxng.org/admin/settings/settings_ui.html) provide
the public schema; the installed source is authoritative for these observations.

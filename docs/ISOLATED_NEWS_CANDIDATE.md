# Isolated News Adapter And Ranking Trial (2026-09-10)

## Latest Decision

The approved guarded trial passed preflight and sent two fixtures, then stopped
on DuckDuckGo News timeout. Keep production unchanged. Neither token-page HTTP
fetch took even one second: the four-second token candidate is not demonstrated
to help. One healthy same-response ranking comparison is promising but too small
to justify deployment. A separate date-loss bug was reproduced offline below.

## Scope And Safety

This is a disposable experiment, not production deployment. Native SearXNG at
localhost:8085, its settings, cache, image, Proton credentials and browser
configuration remain untouched. No model or replacement UI is introduced.

The candidate uses the same digest-pinned image, uid/gid 65534, read-only root,
dropped capabilities, no-new-privileges and resource limits. Scripts/settings
are read-only mounts; temporary files/cache are size-bounded tmpfs. Docker log
storage is disabled. The Python process opens no HTTP listener or published
port. Flask's in-process client exercises native request parsing, plugins,
engine processors, scoring, merging and serialization. This does not test
browser rendering or the production nginx gateway.

Offline tests use network=none. Only the explicit manual live trial shares the
existing VPN namespace and read-only resolver. It cannot access production
cache or VPN keys. It initializes three News adapters plus disabled Brave/DDG
web dependencies needed for their shared network objects; only categories=news
is selected. No new search recipients, host proxies, article fetches or hidden
query expansion. No alternate exit, account, ban reset or automatic retry.

Native suspension state belongs to each process: it is NOT shared with the
candidate. Therefore a disposable process must never be used to bypass a ban.
The manual wrapper checks production error history, refuses unreviewed/long-ban
exception classes, waits 180 seconds and aborts if that history changes. The
operator must avoid concurrent browser searches and review prior failures.
The statistics endpoint lacks suspension expiry timestamps; an unchanged
history is not proof of inactivity or absence of an upstream block. A failed
trial ends the experiment, not permission to restart it with a fresh cache.

## Candidates

- Token fetch: compile the exact installed DuckDuckGo function with only
  timeout=2 changed to timeout=4. Parsing, URL, UA, cache and native network
  context stay intact. The News engine retains its six-second configured
  budget; the network wait subtracts elapsed time (plus native 0.2s overhead)
  for the next request. No global timeout change. This is not a claim that all
  asynchronous network work is instantly cancelled at the engine deadline.
- Ranking: run the original ordering method, then return a new score-sorted
  list from the pre-grouping insertion order for healthy News-only containers.
  Native scores and tie order, all results, thumbnails and dates are preserved.
  Mixed/other categories and degraded responses keep native ordering. This is
  not a freshness or semantic relevance model. Invalid scores fail explicitly.
- Date diagnosis: count standard time/datetime markup in the already-received
  Brave News response. No date is inferred from retrieval time or arbitrary
  text, no additional pages fetched, and no date adapter change is deployed.

Exact source hashes guard all four relevant upstream files. These are
experiment-only runtime replacements, never imported by production. An image
update requires source review; blindly adapting a hash defeats this guard.

## Predeclared Evaluation

Four new public fixtures, fixed before any trial response:

| Id | Intent |
| --- | --- |
| candidate-geothermal | Current reporting on geothermal energy research |
| candidate-coral | Current reporting on coral reef restoration research |
| candidate-water-el | Greek reporting on water scarcity in Greece |
| candidate-fire-el | Greek reporting on forest fire prevention in Greece |

One request per fixture, 20 seconds between successful requests; stop on the
first error, empty result or missing contributor. No retries or baseline
duplicate queries. A fresh tmpfs cache plus measured cache misses establishes
cold token acquisition inside this candidate, without inspecting live cache.
Only healthy three-contributor responses qualify for same-response ranking
comparison. Optional bounded review grades topical intent/language, not factual
accuracy: 2 direct, 1 partial/insufficient snippet, 0 unrelated. Missing dates
remain unknown; within-31-days is a metadata count, not verified freshness.

The token-stage trace stores only cache hit/miss, status classification, HTTP
status and duration in memory. Neither token values, URLs, raw errors nor pages
are printed or persisted. Optional review prints at most five native and five
candidate titles/snippets; treat them as untrusted data, not instructions.

## Preparation Outcome (historical)

The live preflight stopped BEFORE starting the candidate or sending any search
queries: production error-state snapshots differed across the 180-second
cooldown. A follow-up read-only check found three DuckDuckGo News error contexts
where the earlier read had two. Re-serializing the same snapshot compared equal;
this was not reproduced as a hashtable ordering false positive. The wrapper now
also uses an explicitly ordered mapping for deterministic comparisons.

No candidate latency, cold-token success, ranking quality or date-markup result
has been measured. All four candidate fixtures remain unqueried. Production is
unchanged. Resume only during an operator-confirmed quiet window; there was no
candidate failure to retry and no suspension/cache reset.

The production aggregate error history includes timeout contexts in BOTH
fetch_vqd and _send_http_request. This establishes that token acquisition has
failed in production, but not which query/time each failure belongs to or that
a four-second budget would cure it. It also argues against claiming that every
DuckDuckGo failure comes from token acquisition. No raw error payloads retained.

Twelve actual-pinned-source offline tests and native initialization pass,
alongside 32 existing benchmark tests and the full offline validator.
The first offline harness attempts caught a missing PYTHONPATH and the missing
disabled Brave network dependency; both were corrected before any live query.

Offline entry point (also called by validate.ps1):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-news-candidate.ps1
```

Live use requires deliberate cooldown review and an operator-confirmed quiet
window, not scheduled health polling. Do not rerun failed fixtures. No candidate
change is ready to deploy without the missing live evaluation.

## Confirmed Quiet-Window Follow-up (historical)

The user subsequently confirmed a quiet window. The first new preflight again
stopped before launching the candidate because the error snapshots differed.
Read-only diagnosis found one production SearXNG worker, six matching immediate
sanitized statistics snapshots and no established host connection to port 8085
at the instant inspected. The pinned metrics counters are cumulative, not
time-decayed. These checks rule out the observed multi-worker hypothesis but
do not identify the traffic source or prove that the whole window was idle.

Added ten seconds before taking the baseline to allow an already-in-flight
request to finish; the configured maximum engine budget is eight seconds. The
full 180-second cooldown and strict comparison remain intact. Pending requests
were only a hypothesis. One additional manual preflight with this settling
interval ALSO stopped on changed history: this change did not fix the blocker.

Neither invocation sent a candidate query. All four fixtures remain unqueried;
there are still no live token-timeout, ranking-quality or date-markup findings.
Production config, cache, provider selection, credentials and VPN were not
changed or restarted. No ban reset, exit rotation or upstream retry occurred.

The full offline validator passed twice, including after the settling change:
32 benchmark tests, 12 candidate tests, 14 negative Compose cases and native
privacy/offline-egress/recovery checks. Final live ops passed with the original
three healthy services and VPN-only search. No image builds apply; no reboot,
live VPN interruption or browser automation was performed in this follow-up.

At that handoff, the recommended next scope was a
bounded investigation of caller/connection metadata to explain ongoing changes,
without search terms, browser history, command-line contents or persistent
request logs. Gateway interruption or content capture requires a separate
decision. No production adapter/ranking deployment is justified yet.

## Caller Metadata Audit (historical)

The subsequently approved metadata audit did not identify a background caller:

- Windows: 104 snapshots over 60 seconds found no clients of loopback 8085.
- Search namespace: 862 snapshots over 90 seconds found five loopback TIME_WAIT
  socket states, consistent with health checks. Actual container health commands
  request root every 30 seconds, not search. No HTTP contents were inspected.
- Only expected containers belong to the three AnonExplo networks. The host
  listener is com.docker.backend; live nginx targets the verified VPN namespace.
  Proxy-bypassed host statistics match the direct in-container aggregate counts.
- Engine error history stayed unchanged over a 40-second comparison and then
  a full 180-second window. During the latter, 310 host TCP snapshots found only
  one PID-0 TIME_WAIT connection, not an attributable application. The audit's
  own preceding stats read is a plausible origin, not a proven attribution.

These are bounded samples, not a guarantee that no short-lived/internal caller
ever existed. They cannot identify who caused earlier changes. The earlier
suggestion of a background application remains unproven; do not stop an app on
that basis. No queries, browser history, command lines, packets or persistent
request traces were collected. No production configuration or process changed.

All 44 offline Python tests, 14 negative Compose cases and full native privacy,
offline-egress/recovery checks passed. No image build contexts exist. The live
candidate has still sent no query and no ranking/timeout fix is deployed.

The service was quiet for the measured full cooldown-length window. The next
step is the existing bounded trial when approved, not more caller hunting.
Keep its stop guard: current quietness does not predict future engine health.

## Completed Guarded Trial

Branch stamos/guarded-news-trial from ac26c25. User approved resuming; preflight
and VPN checks passed without weakening cooldowns. No production change or
restart. The validator was deferred until after the live measurement to avoid
competing Docker validation load. Requests stayed 20 seconds apart.

| Fixture | Rows | Contributors | Total seconds | Cold token-page HTTP | Outcome |
| --- | ---: | ---: | ---: | --- | --- |
| candidate-geothermal | 89 | 3 | 1.49 | 200 in 0.41s | Healthy comparison |
| candidate-coral | 45 | 2 | 6.00 | 200 in 0.25s | DDG News timeout; stop |

First response engine counts: Brave News 44, DDG News 27, Reuters 20 (overlap
explains the sum exceeding merged rows). Second response: Brave News 37,
Reuters 8, no DDG result. Both had measured cache misses in a fresh tmpfs cache.
The two Greek fixtures were NOT sent. No retry, provider polling, exit change,
ban reset, article fetch, raw error trace or persisted response/token.

The second failure occurred after the token-page HTTP call returned. No parsed
token-presence flag/value or downstream HTTP trace was captured, so HTTP 200
must not be equated with successful token extraction or a conclusively traced
downstream failure. It does establish that waiting for the token page was not
the timeout in this sample. Neither sample demonstrates benefit from a 2 -> 4s
token limit. Do not raise global limits or claim this cures DDG reliability.

### Limited Ranking Review

On geothermal, score-only ordering replaced one top-five member, promoting a
topically relevant item with publication metadata less than a day old. Native
top-five dated count 1 -> 2; within-31-day count 0 -> 1. A Reuters result roughly
1,069 days old remained in both lists. Missing dates were not treated as fresh.

Manual topicality grades (2 direct intent, 1 partial/insufficient, 0 unrelated):
native 2,1,1,1,1; candidate 2,1,2,1,1. Generic reference/report pages and opinion
material were treated as partial for the requested current research reporting.
These are snippet judgements, not factual or publication-date verification.
Only one healthy English case was reviewed; no broad ranking-quality claim.
Coral's degraded response was not graded or compared. First two fixtures now
are observed cases, not unseen evidence for subsequent retuning.

### Publication-Date Findings

The 44 geothermal and 37 coral Brave News nodes had no standard time elements
or datetime attributes. This does NOT establish that the full HTML has no date
information; no broader date parser was demonstrated or introduced.

The healthy response also contained Brave/DDG duplicate results with missing
dates. Pinned source merge_two_main_results copies missing fields through
defaults_from only when both rows have the same result type. Brave News emits
LegacyResult; DDG News emits MainResult with publishedDate. A synthetic, purely
in-memory probe confirmed that merging a dated MainResult into an undated
LegacyResult preserves both engine names but leaves the date missing. This
reproduces a metadata-loss path, not the arrival order of every observed row.
No production merge code was changed. Investigate this as a separate scoped,
test-covered fix rather than inventing dates or introducing an LLM.

### Closeout

All 44 offline Python tests, 14 negative Compose cases and full native privacy,
offline-egress/recovery checks passed after the trial. The additional in-memory
merge probe passed without requests. Production ops confirmed the original three
healthy services and unchanged localhost/VPN routing. The disposable candidate
was removed automatically; production cache, keys, images and settings remain.
No image build contexts or installable release apply; no reboot, live kill-switch
drill or browser automation ran. No timeout, date or ranking fix is deployed.

Next: a narrowly tested cross-type date-merge repair, with DDG downstream request
diagnosis separate. Do not rerun this failed suite or deploy the ranking candidate
on one healthy query.

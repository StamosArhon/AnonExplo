# Implementation Roadmap

## Product Objective

AnonExplo is a private, locally operated SearXNG browser-search platform.
The UI is SearXNG at `http://127.0.0.1:8085`, and Brave's search template is
`http://127.0.0.1:8085/search?q=%s`. No chatbot, LLM, query rewriting, or
orchestrator is required on this path. AI is deferred unless a local-only
experiment demonstrates useful relevance gains within an acceptable latency.

## Architecture And Privacy Baseline

Brave -> localhost host-gateway:8085 -> SearXNG in search-vpn's namespace ->
Proton WireGuard -> configured search engines. DNS is pinned to the VPN-local
resolver; no host-wide VPN or direct-provider outage fallback. Preserve the
restricted, ignored per-PC credential. Upstreams still receive plaintext
queries and can potentially retain them. Browser clicks remain outside this VPN.

The old UI, backend, fetcher, model runtime and provisioner are now removed from
source and deployment. Only host-gateway, search-provider and search-vpn remain.
User explicitly chose removal, not opt-in legacy profiles. Future local result
refinement may be headless and does not require a separate AnonExplo interface.
Code before removal remains recoverable at bdb14ad in Git; no local user data
or cached Docker images are deleted by this migration.

## Current Holdout And News Diagnosis Scope (2026-09-10)

- Completed scope stamos/holdout-news-ranking from clean main db95831; user
  authorized unseen-question evaluation and deeper News ranking investigation.
- Implementation 7c22ed9 was pushed to origin. This documentation closeout
  accompanies the reviewed fast-forward main merge and branch cleanup. Resume
  future work from updated main; no remote blocker remains.
- Added six fixed EN/EL informational holdouts and four News holdouts, declared
  before querying. Existing production settings/weights remain unchanged. No
  live plugin, model, new provider, restart, key/exit change or browser edit.
- Informational holdout: 6/6 nonempty, 32-34 rows, three web contributors each,
  zero errors, mean 1.18s. Two of 30 top-five positions were unrelated, both
  Bing. No retuning on the holdout; snippet grades/limitations are recorded in
  HOLDOUT_AND_NEWS_RANKING.md. No comparison against weight 1.0 was run.
- News: first unseen query stopped on DuckDuckGo News timeout (2.06s). After
  cooldown, one deliberate suffix invocation tried the second unseen query;
  the same engine timed out (2.04s). No failed query retried; remaining two
  Greek cases were not sent. No healthy live score-order comparison obtained.
- Source diagnosis: native scores ignore publication age; post-score grouping
  uses template/category/thumbnail presence and can promote lower-score rows.
  Brave News does not populate publication dates. DuckDuckGo token fetch uses
  a hard-coded two-second request before the actual News endpoint. Timings fit
  that stage, but no live HTTP trace proves it. Prior success can be warm-cache
  dependent; query/UA token cache exists, but contents were not inspected.
- Added same-response score-only replay with no additional requests or live
  effect; sanitizes metrics, rejects invalid scores, retains tie order, skips
  degraded comparisons. Optional bounded review displays candidate top five.
  StartAt selects an explicit manual suffix, never automatic retry/resume.
- Added offline characterization using the real pinned ResultContainer/scorer.
  First validator attempt failed because metric storage was uninitialized in
  this test-only process. Stubbed counters only, not ranking or normalization.
  Final full validator passed: 32 benchmark tests, 14 negative Compose tests,
  generated startup checks, native ranking characterization, settings/privacy,
  offline direct-egress blocking and stopped-search recovery. Isolated cleanup
  passed. Image builds remain N/A (no contexts; Compose build succeeds).
- No production ranking change is justified by these partial News results.
  Candidate adapter/ranking repair needs a separate, reversible isolated trial;
  don't increase global timeouts or enable more recipients as a substitute.
- Final live ops passed: three healthy services, localhost 8085, VPN namespace,
  DNS and distinct egress. Production settings/Compose diff is empty. No new
  kill-switch/reboot drill or browser UI automation was needed/performed.
- Reviewed changes against main, whitespace checks passed, remote main matches
  local. No secret files tracked. Evaluation tools and diagnosis are complete;
  the next adapter experiment must use a fresh branch and separate scope.
  No installer/release applies to benchmark/documentation-only changes.

## Previous Relevance And Coverage Scope (2026-09-10, historical)

- Completed scope: stamos/relevance-and-coverage, from clean main 3e2fc4e.
  User authorized broader informational/news evaluation and evidence-backed tuning.
- Implementation commit ec13674 was pushed to origin. This documentation closeout
  accompanies the reviewed fast-forward main merge and branch cleanup. Resume
  future implementation from updated main; no remote blocker remains.
- Extended manual browser benchmark: six navigation, six informational and four
  news fixtures; separate Anytime/month cases, language comparison, explicit
  single-engine diagnostics, recipient/filter eligibility and freshness metadata.
  Optional bounded public-fixture review supports manual rubric grades; default
  output remains sanitized metrics. No browser history, payload files or AI.
- Consolidated old engine coverage helper onto the hardened benchmark to remove
  raw upstream error printing and inherited redirects/proxies. Engine/category
  selectors are never combined (SearXNG unions them). Tests stop on degradation.
- Baseline informational run: 6/6 nonempty, 24-36 rows, three web contributors,
  no engine errors, mean 1.25s. Manual top-five inspection found five clearly
  irrelevant positions across 30. Explicit language failed to cure Bing's
  unrelated matches; sixth sample hit Brave rate limiting and the run stopped.
- Preserved the configured 180-second rate-limit cooldown; no exit/key/ban reset.
  Worked on offline validation before restarting SearXNG after the cooldown had
  elapsed. Increased manual benchmark pace to 15 seconds; not a no-limit promise.
- Changed only Bing weight 1.0 -> 0.35 initially, retained all providers. Live
  six-question comparison: 6/6 nonempty, three contributors, no engine errors,
  mean 1.09s; clearly irrelevant top-five positions fell from five to two.
  Sequential small-sample observations, not a controlled causal or speed claim.
- News-month exposed eligibility loss: only Reuters supports the time filter;
  English fixture 20 rows, Greek zero, test stopped. Anytime news: 4/4 nonempty,
  70-92 rows, 2-3 contributors, no errors, mean 1.23s. Some highly ranked Reuters
  items were years old. Trialled supported display_date:desc ordering: four
  nonempty/error-free runs, mean 1.09s. Space top-five recent metadata rose from
  zero to two but an unrelated item entered; rejected that change and restored
  original Reuters ordering. No news ranking change is shipped.
- Full isolated validator passed for Bing trial: 24 benchmark unit tests,
  14 negative Compose tests, generated startup syntax, pinned topology, native
  privacy/engine settings, direct-egress block and stopped-search recovery.
  No custom image build contexts remain; Compose build succeeds with no builds.
- Reuters candidate also passed the full validator, but was rejected for manual
  relevance reasons, not runtime failure. Final validator passed after rollback:
  same 24 unit/14 negative policy cases plus complete offline UI/recovery checks.
- Retired outdated coverage instructions into LEGACY_SEARCH_ENGINE_COVERAGE.md;
  current docs no longer recommend restoring backend or editing old .env keys.
- Reviewed retained code/config/docs against main; whitespace checks passed and
  remote main was synchronized. No .env or VPN key files are tracked/modified.
  No new recipient/account, image update, browser profile edit, model, telemetry,
  query storage or saved result payload. No live VPN-stop/reboot/sleep drill in
  this scope: network topology and existing kill switch are unchanged.
- After restoring Reuters ordering, final navigation regression passed: six
  expected sites rank 1, three contributors each, zero engine errors, mean 1.71s
  (one request 3.98s). No claim of a latency improvement. Live ops passed: three
  healthy services, unchanged localhost 8085, VPN namespace/DNS/distinct egress.
- Implementation, validation and live settings deployment complete. No release
  artifact applies to local settings-only deployment. Follow-up must start from
  updated main, not reuse this completed branch.

## Previous Removal Scope (2026-09-10, historical)

- Completed scope: stamos/remove-legacy-stack; handoff target main.
- Implementation commit a3e2fd4 was pushed to origin. This documentation
  closeout accompanies the reviewed fast-forward merge and branch cleanup;
  resume future work from updated main. No remote blocker remains.
- Removed 20 tracked legacy app/runtime/provisioner files, legacy Compose
  services/network, UI/API gateway listeners, obsolete model/backend .env.example
  keys and startup dependencies. Existing .env and credentials are untouched.
- Base Compose search is now internal-only/offline; Proton overlay is the only
  supported production egress. Validator uses its own tmpfs cache, not live data.
- Reworked validation/ops to assert exactly three production services and one
  localhost port. Fourteen negative Compose policy tests cover legacy-service/
  port reintroduction, direct egress and VPN security regressions. Ten offline
  benchmark tests remain; deleted app tests are not claimed as current tests.
- Generated-startup tests cover script syntax, quoted paths, hidden launchers,
  Docker-start switch, VPN-only dispatch and preserved browser-helper JS syntax.
- Startup refreshed without browser profile changes. Hidden task completed with
  result 0. Migration removed the exact UI/backend/fetcher containers, unused
  model network and old redirector task/process. No model container was running.
  Ports 3001, 8001 and 8095 closed; only localhost 8085 remains published.
- Live ops check passed: three healthy services, native UI/privacy headers and
  VPN namespace/DNS/distinct egress. No browser storage or search cache erased.
- First validator attempt caught a leftover model-network YAML block; corrected.
  Subsequent validation passed. Expanded startup test initially false-matched
  SEARXNG_UI_PORT as the removed UI_PORT; corrected to whole-token matching.
  Final expanded validation passed: 14 negative policy cases, 10 benchmark unit
  tests, generated startup/browser-helper checks, Compose config, native UI,
  settings/headers/catalogue, offline direct-egress blocking and outage recovery.
- Live VPN-stop drill passed: direct-IP HTTPS, direct public DNS and IPv6 were
  blocked. Recovery recreated only the three intended services and passed
  namespace/DNS/distinct-egress checks. Post-recovery six-fixture browser run:
  6/6 expected hosts rank 1, no engine errors, mean 1.15s. This is a limited
  navigation smoke baseline, not proof of general relevance or improved speed.
- Reviewed removal/config/scripts/docs against main; whitespace checks passed.
  Credential files are not tracked. No browser profile automation, reboot or
  sleep/resume drill ran; hidden startup was exercised through Task Scheduler.
  Cached images and inert helper files remain intentionally; no broad pruning.
- Build check now reports no services to build: no custom build contexts remain.
  All three production services retain existing digest-pinned upstream images.
  No desktop installer/release applies. No LLM installed or benchmarked.

## Previous Browser Baseline Handoff (historical)

- Implementation branch: `stamos/browser-search-baseline`; verified handoff target: `main`.
- Implementation commit `f48458b` was pushed successfully to origin; the final
  documentation closeout accompanies the reviewed fast-forward merge/cleanup.
  No remote blocker remains. Resume future implementation from updated main.
- Scope: direct browser route privacy/recovery, native preference safeguards,
  synthetic browser-path benchmark, and documentation rebaseline.
- No new providers/accounts, no model downloads, no browser profile/cookie edits,
  no query history database, no scheduled searches, no VPN exit rotation.

## Milestones

1. `browser-search-baseline` (implemented and validated): document the real product; safeguard
   the native UI; recover gracefully from search-container address changes;
   test instance-default Greek/English search without the legacy backend.
2. `search-only-deployment`: remove legacy services/code by user decision; reduce
   published ports/startup dependencies; update health/recovery/validation together.
   Preserve user data and port 8085. Implemented, migrated and validated.
3. `relevance-and-coverage`: expand the synthetic suite with manual relevance
   judgements for informational/news queries; compare language and engine choices;
   tune only when evidence supports it. Evaluate image/video coverage separately
   with proxied thumbnails and an explicit recipient review. Informational/news
   work and the independent holdout diagnosis are complete; no live News reranker
   has shipped. Media/new recipients remain deferred.
4. `reliability-maintenance`: validate reboot/sleep/resume and VPN interruption;
   keep digest-pinned update/rollback procedures and local aggregate diagnostics.

## Previous Browser Baseline Findings And Validation (historical)

- Initial six-query benchmark through 8085 with no cookies/engine overrides and
  an English browser locale: six expected domains at rank 1, no engine errors,
  three contributing web engines on every query, mean response 1.18 seconds.
  Includes three English and three Greek public fixtures. This is a small
  navigational baseline, not proof of general relevance or future availability.
- No basis yet to impose a global Greek filter, change engine weights, expand
  every query, or re-enable failing providers. Keep user's explicit language,
  engine and category choices available.
- Explicit-language comparison: six expected domains again rank 1, no engine
  errors, three contributing web engines per query, mean 1.19 seconds. Locale
  affects result mix but did not improve this navigation metric. Sequential
  runs are not a controlled performance experiment.
- Full validator passed twice after fixing the new test harness's missing local
  favicon-catalogue initialization. The first attempt failed only that harness
  after builds and existing tests passed; isolated cleanup completed. Final run:
  10 offline benchmark tests, 66 backend tests, 19 fetcher tests, managed image
  builds, Compose/base/VPN policies, script syntax, engine catalogue, privacy
  locks (including stale cookie values), headers and local HTTP smoke passed.
  No live upstream queries were sent by the validator.
- Isolated stopped-search drill returned HTTP 503, no Location, no-store and
  no-referrer; restart restored search without replacing the gateway. This tests
  outage/restart recovery, not a forced Docker-IP-change or PC reboot drill.
- Deployed by validating/reloading nginx and restarting only SearXNG to load
  settings. VPN namespace/credential/host networking unchanged. Live VPN health,
  VPN-local DNS and distinct egress passed. All six services healthy. Root,
  preferences, config and stats returned 200 with privacy headers. A native
  HTML public-fixture search rendered results with no query in the page title.
- Optional model probe skipped: GGUF absent and AI not required. Browser profile
  automation, visual interaction, reboot/sleep/resume, forced IP replacement and
  a fresh VPN-stop drill were not run in this scope.
- Reviewed code/config/docs against main; remote main synchronized; whitespace
  check passed; no .env or Proton credential files tracked or modified.

## Previous Browser Baseline Implementation (historical)

- Native SearXNG preferences lock autocomplete/favicons off, image proxy on,
  query-in-title off, so stale preference cookies cannot weaken those defaults.
- Port 8085 adds no-store/no-referrer headers; suppresses query-bearing gateway
  error logs and proxy response temporary files; returns a local 503 on gateway
  upstream failures with no external fallback. Dynamic Docker DNS refreshes
  the fixed upstream name after address changes. No extra search retries.
- Setup script now configures direct 8085 for future browser setups and disables
  external redirector fallback unconditionally. Existing browser profiles and
  generated host helpers are not rewritten in this scope.
- Manual `test-browser-search.ps1` verifies VPN health/namespace/DNS/egress and
  localhost port ownership before a paced fixed-fixture run. Reports only ids,
  counts, rank proxies and latency; refuses redirects and stops on degradation.

## Security Assumptions And Limits

- GET searches from Brave remain visible in its address bar and potentially
  browser history/sync. HTTP no-store and hidden query titles do not erase this.
- Proxied images travel through SearXNG's egress, but are additional requests to
  image hosts. External links/media deliberately opened by the user retain
  normal browser networking. No zero-third-party-contact promise.
- Native engine cooldowns are preserved. Root/container health is availability
  of the local service, not a guarantee of successful upstream search.
- No installable desktop release applies; deployment is local Docker config.

## Exact Next Steps

1. Preserve port 8085, privacy safeguards, engine choices and the VPN profile.
2. Preserve the evaluated Bing weight and expanded benchmark. News ordering is
   unchanged after rejecting the newest-first trial. Retain honest limits of
   snippet-level judgements, news freshness and intermittent upstream errors.
3. Next recommended scope: isolated candidate adapter/ranking repair, grounded in
   HOLDOUT_AND_NEWS_RANKING.md (token budget, score-vs-layout grouping, missing
   dates). Require healthy cold-query tests and topicality review before deploy.
   Ask before the new scope. Media, headless models and reboot drills are separate.

## Continuity

Read AGENTS.md, this roadmap, INSTRUCTIONS_AND_NOTES.md, ARCHITECTURE.md,
and SECURITY_PRIVACY.md. Prior evidence is preserved in
LEGACY_IMPLEMENTATION_ROADMAP.md; its LLM roadmap and fallback advice are superseded.

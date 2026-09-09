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

## Current Removal Scope (2026-09-10)

- Branch: stamos/remove-legacy-stack; handoff target main.
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
   with proxied thumbnails and an explicit recipient review.
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
2. Finish removal closeout/review/push/merge/branch cleanup. Next scope should be
   relevance-and-coverage with richer informational/news fixtures and manual
   judgements, not restoration of a chatbot. Ask before starting that milestone.
3. Later quality work needs richer informational/news fixtures and manual
   judgements, not global language/weight changes based on six navigation cases.

## Continuity

Read AGENTS.md, this roadmap, INSTRUCTIONS_AND_NOTES.md, ARCHITECTURE.md,
and SECURITY_PRIVACY.md. Prior evidence is preserved in
LEGACY_IMPLEMENTATION_ROADMAP.md; its LLM roadmap and fallback advice are superseded.

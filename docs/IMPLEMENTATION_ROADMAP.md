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

## Current Guarded Web Candidate Batch (2026-09-10)

- Approved implementation/offline-test/readiness batch on
  stamos/guarded-ddg-web-candidate from clean main 637ade0.
- Added explicit hash-pinned upstream source provisioning, a guarded first-page
  adapter executor, pure policy tests and exact-upstream mocked pipeline tests.
  HTTPS host/path restrictions, no redirects, header filtering, bounded challenge
  arithmetic, shared deadline and no query cache/retries. No JS execution.
- Runner is offline-only, non-root/read-only with network=none and capped tmpfs;
  no VPN/key/live cache/ports. -Live refuses. Optional validate.ps1 -WebCandidate
  requires explicit provisioning and never downloads during validation.
- Full validate.ps1 -WebCandidate passed: 110 Python test executions (including
  12 new host guards and 18 new exact-adapter mock tests), 20 negative Compose
  cases, seven negative identity cases plus equality, source/binding checks,
  isolated managed build with production tag unchanged, native privacy/settings/
  ranking, blocked egress, outage/recovery and cleanup. -Live refusal passed.
  Optional old transport-version comparison not repeated. Read-only source
  inspection recovered from an import-time missing-/tmp error; no product impact.
- Readiness decision: no live trial yet. This direct adapter executor is not a
  native processor/cooldown integration; real transport/cookies/cancellation need
  offline checks first. See GUARDED_DDG_WEB_CANDIDATE.md. No production repair,
  relevance gain, image deployment, new engine enablement or News fix claimed.
- Reviewed code/docs accompany commit/push, fast-forward main merge and scoped
  local/remote branch cleanup. No installer/release or deployment applies.

## Previous New-Adapter Applicability Review (2026-09-10)

- User requested proceeding after the completed batch. Read-only upstream check
  found unchanged client releases but new SearXNG revisions 765a999 (DDG web) and
  42e1d61 (Startpage). Scope stamos/new-ddg-adapter-review from main 3200f4c.
- Reviewed exact patches and local engine selection. Web is opt-in; News's
  duckduckgo_extra.py token-fetch path is not repaired by this change. Do not
  deploy as a News timeout fix or activate Startpage's proof-of-work handling.
- New DDG web follow-up joins a response-derived URL without a host check in that
  function. Pure local URL-joining probe confirms absolute/scheme-relative URLs
  can replace the base origin. This is a review concern, not a demonstrated
  exploit; no upstream code/challenge executed and no provider queries sent.
- Next distinct candidate would need offline origin/redirect/parser/budget tests
  before any web engine trial. Production remains unchanged. See
  NEW_DDG_ADAPTER_REVIEW.md. Full validator passed: 80 baseline Python tests,
  20 negative Compose cases, seven negative identity cases plus equality, managed
  isolated build with production tag unchanged, source/binding/privacy/settings,
  ranking, blocked egress, outage/recovery and cleanup. Optional old candidate
  comparison not repeated. Reviewed docs accompany push/main merge/branch cleanup;
  no deployment or release. This applicability review is complete.

## Previous Upstream Comparison Batch (2026-09-10)

- User requested 2-3 bundled steps. Scope stamos/upstream-transport-review from
  main c70807d: upstream review, offline candidate comparison, full validation and
  Git closeout; no routine approval pauses or production/live-query changes.
- Reviewed curl_cffi 0.16.3, curl-impersonate 2.2.2, curl 8.22 timing changes and
  SearXNG master ba055b3. SearXNG still pins 0.16.1; recent engine additions do
  not fix the timeout. The newer Python client still bundles libcurl 8.21.
- Added explicit hash-pinned provisioning and a disposable offline wheel overlay;
  production source guards remain strict and separate from reviewed candidate
  hashes. No runtime installation/download, VPN access, key/cache or host ports.
  Only the candidate tmpfs allows library executable mappings; /tmp stays noexec.
- Initial loader setup failed on noexec and then the wrong libc wheel. Verified
  glibc/x86_64/CPython and selected the correct manylinux artifact; no product
  restart or provider retry. 44 host tests and 24 candidate tests now pass.
- Candidate reproduces the same misleading TLS-stall counters; no demonstrated
  improvement. Retain production unchanged. See UPSTREAM_TRANSPORT_REVIEW.md.
- Full validate.ps1 -TransportCandidate passed: 80 baseline + 24 candidate Python
  test executions, 20 negative Compose cases, seven negative identity cases plus
  equality, source/binding checks, managed isolated build (production tag
  unchanged), native privacy/settings/ranking, blocked egress, outage/recovery
  and cleanup. Live/invalid candidate modes refuse. Three production services
  remain healthy by read-only Docker metadata; no live search tests were sent.
- Three-step batch complete. Reviewed tooling/docs accompany commit/push,
  fast-forward main merge and scoped local/remote cleanup. No release/deployment
  applies. Keep production and the offline reproduction until a relevant upstream
  fix or separately scoped, materially different candidate warrants evaluation.

## Previous Offline Timeout Review (2026-09-10)

- User approved offline client review. Fresh stamos/offline-timeout-semantics
  from clean main 2243b6b; no new live search, production change or upgrade.
- Added source-guarded native caller/retry tests and controlled loopback transfers
  in a network-disabled container, using the existing hardened wrapper with
  -TimeoutSemantics. Numeric-only output, no production cache/key, no host ports.
- Reproduced the misleading live counter pattern during a local TLS-handshake
  stall, both cold and after successful handle use: server accepted TCP but
  counters show zero TCP/TLS and first-byte time near timeout despite no response.
  TLS stalling is consistent with the live sample, not proven as its root cause.
- Confirmed caller-vs-transport budget divergence and lack of explicit caller
  future cancellation; native transport timeouts retain code/identity. Timeout
  gets no native Network retry at retries=0, but ConnectionError gets one.
- Initial retry mocks failed on read-only instance methods; corrected test-only
  class patch. All 11 new tests passed. See OFFLINE_TIMEOUT_SEMANTICS.md.
- Full validation passed: 77 Python tests, 20 negative Compose cases, seven
  negative identity cases plus match, offline source/binding checks, isolated
  managed build (production tag unchanged), privacy/settings, blocked egress,
  outage/recovery and cleanup. Live/mixed-mode refusal checks passed. Docker
  metadata confirms the same three production services remain healthy.
- Review complete; tests/docs accompany commit/push, fast-forward main merge and
  scoped branch cleanup. No production timeout/TLS/cancellation change, restart,
  provider query, installer or release. Live DDG reliability remains unresolved.
  Next scope: upstream transport source/release review and offline compatibility
  checks before proposing any guarded image update or fresh live experiment.

## Previous Approved Reliability Batch (2026-09-10)

- User approved four bundled steps: repair image checks/build isolation; obtain
  bounded transport timings; implement only an evidence-supported search fix;
  validate, deploy proven changes and close Git. No approval pause between normal
  steps/branches. Escalate real blockers, privacy/security changes, cost or scope.
- First branch stamos/image-validation-isolation from main 7db138a compares exact
  Linux platform manifests, rejects missing/invalid/mismatched descriptors, and
  uses anonexplo/searxng:validation only in the offline validation project.
  Validator verifies the production tag remains unchanged across builds.
- Live ops passes without a production restart or retag. Full validation passed:
  seven negative identity cases, 20 negative Compose cases, 62 Python tests,
  isolated build (production tag unchanged), native privacy/egress/recovery.
  Cleanup passed. No model/provider/network/settings change. This completed unit
  accompanies the reviewed push/merge/branch cleanup; continue the approved batch
  with transport diagnosis on a fresh branch, without another approval prompt.
- Step one merged/cleaned as 92202a1. Step two stamos/ddg-transport-timings adds
  source-guarded, numeric-only transport counters on the native client, with two
  new frozen fixtures. No timing/network/fingerprint changes. Offline preparation
  passed 41 host tests, native hook initialization and fake-transfer bindings.
- Bounded live trace completed: battery returned 23 rows in 1.000s with healthy
  token/news transfers. Wetlands then timed out during token HTTP in 2.003s;
  zero rows, one error, no downstream request. Stopped without retry. Short DNS
  timing but zero TCP/TLS completion counters and contradictory first-byte timing
  do not establish the precise network/root cause. See DDG_TRANSPORT_TIMINGS.md.
- Conditional step three: no evidence-supported production search fix identified;
  deliberately retain native timeouts, cooldowns, providers, routing and ranking.
  Both completed fixture sets now refuse PowerShell -Live; no further live trial
  in this batch. Offline instrumentation remains covered by normal validation.
- Step four: full validation passed: 66 Python tests, 20 negative Compose cases,
  seven negative identity cases plus positive match, native offline hook/binding
  checks, isolated image build with production tag unchanged, privacy/settings,
  blocked egress, outage/recovery and cleanup. Live-mode refusal verified without
  queries; final live ops passed with three healthy services and VPN isolation.
  Reviewed diagnostic/docs unit accompanies push, fast-forward merge and scoped
  branch cleanup. No production deployment/restart or desktop release required.
- Approved batch complete: operational checker/build isolation fixed; bounded
  transport diagnosis delivered; conditional search fix deliberately declined;
  final verification complete. The intermittent upstream issue remains open.
  Next useful milestone is an offline review of the pinned client's failure-path
  timing semantics before proposing any further narrowly scoped live experiment;
  no repeated provider probing or new experiment is authorized by this closeout.

## Previous DDG Request Diagnosis (2026-09-10)

- User approved investigating the remaining DDG News timeouts. New scope branch
  stamos/ddg-request-diagnosis from clean main 25a8425. No production fix/change.
- Read native adapter/processor/network: cold token HTTP and downstream news
  request share the six-second engine budget; token HTTP retains its own 2s
  limit. Synchronous waiter has 0.2s overhead and no explicit future cancellation.
- Added bounded, metadata-only native-call observation and two new frozen public
  fixtures; do not retry the old failed suite. Native arguments/results/errors
  and limits remain intact. Offline preparation passed 37 host tests and native
  network-none initialization. See DDG_REQUEST_DIAGNOSIS.md for evidence/limits.
- One live run passed the full cooldown/VPN/image preflight. ddg-wind: cold cache,
  token HTTP timeout in 2.002s (transport budget 2s, waiter 2.199s); native web
  response 2.038s, zero rows, one error. No token response/parsing completion,
  downstream request or news parsing occurred. Stopped; Greek fixture unqueried.
- This confirms a token-fetch failure in this sample, distinct from the earlier
  failure after a fast token-page HTTP return. DNS/TCP/TLS/server-read cause is
  not established. No global timeout/provider/routing change or fix justified.
  No rerun; diagnostic -Live now refuses immediately. Full validator passed:
  62 Python tests, 18 negative Compose cases, managed build, native initialization,
  ranking/privacy/offline-egress/recovery. Temporary resources removed.
- Cached validation rebuild changed the OCI index/attestation but not the runtime
  platform manifest. Final ops-check fails its top-level ID comparison; read-only
  platform descriptor comparison proves identical sha256:1f98d2d96d53e188a371cd13e3e439c94aafca027dbfc1ef8179977ad5d6396a.
  The old index cannot be inspected locally anymore. No retag, code fix or
  production restart attempted. Independent VPN/DNS/distinct-egress and native
  localhost/privacy checks passed; deployed search remains healthy.
- This exposes a separate pre-existing health-check/validation-image identity
  bug, not a DDG cause. Recommend a scoped checker/validation-tag correction
  before the next content-free transport-phase diagnostic on a fresh fixture.
  Do not weaken image identity to tag-only or restart to hide the false alarm.
  Diagnosis/tooling complete; fa0e3a0 committed and pushed, diff reviewed against
  unchanged remote main, whitespace checks passed. This documentation closeout
  accompanies the fast-forward main merge and local/remote branch cleanup.
  No remote blocker; the checker defect remains explicitly open, not fixed.
  No deploy, release, browser history, provider config or credential change.

## Previous Publication-Date Repair (2026-09-10)

- User approved fixing the confirmed duplicate-date loss. Fresh branch
  stamos/preserve-publication-dates from clean main 15159dd. No ranking/timeout,
  provider, VPN, browser-profile or legacy-product expansion.
- Original pinned-image regression fails for all four MainResult/LegacyResult
  pairings: explicit None is not filled even in same-type defaults_from. Repair
  only missing dates from incoming datetime; preserve existing dates and all
  non-date merge/rank fields. Native legacy pubdate class attribute also shadows
  its dictionary key: one guarded HTML macro item lookup corrects date markup.
- Added images/searxng: digest-pinned base, exact guards on two upstream files,
  network-disabled build steps, tiny allowlisted context and 13 native regression
  tests. Local versioned image replaces the old environment image override.
  No credentials/cache in build context, source bind mount or runtime patching.
  Existing gateway/VPN images, capabilities, routes and settings remain unchanged.
- First original-image probe lacked a temporary writable directory; rerun with
  tmpfs reproduced all four missing-date failures. Two initial repair builds
  correctly failed date-display tests, exposing legacy attribute shadowing;
  native source review led to the guarded template correction, not weakened
  rendering assertions. Full validator passed after correction and again with
  the final 13-test JSON-inclusive suite: 57 Python tests total, 18 negative
  Compose cases, managed image build, native ranking/settings/privacy, offline
  direct-egress block and outage/recovery. Isolated resources cleaned up.
  Original-image HTML regression also failed as expected. Historical -Live
  refusal verified without queries. See PUBLICATION_DATE_REPAIR.md.
- Deployment preflight reviewed aggregate error classes (timeout/rate-limit,
  access-denied and generic parse/HTTP failures), allowed in-flight settling and
  observed unchanged history across the full 180-second cooldown. No CAPTCHA/
  Cloudflare long-ban class was present; no ban/cache/exit reset or search query.
  This is not proof of no user activity or guaranteed upstream availability.
- Deployed by replacing only search-provider from the validated local build.
  Gateway and VPN container IDs unchanged. Live ops passed: matching local image
  ID, three healthy services, localhost 8085, native privacy headers, shared VPN
  namespace, VPN-local DNS and distinct working search egress. Credentials,
  production cache, browser profiles and search settings untouched. No reboot,
  live VPN-stop drill, installer or registry image publication applies here.
- Final deployed-container date regressions passed (13 tests in a separate
  process, no worker mutation/engine requests); root/preferences/config/stats
  all returned 200 with no-store/no-referrer. This is deterministic metadata
  verification, not a new live relevance or reliability benchmark.
- Implementation 71b8dba committed and pushed. Reviewed all changes against main;
  whitespace checks passed, no credential files tracked, remote main unchanged.
  This documentation closeout accompanies the fast-forward main merge and
  local/remote branch cleanup. No remote blocker. Resume future work from updated
  main on a fresh branch; the completed repair scope must not be reused.
- Historical candidate live mode retired immediately; original-image offline
  tests remain historical characterization. Do not retry the failed News suite.
  Next separate scope remains bounded DDG downstream-request diagnosis, not
  global timeout increases or ranking deployment. No upstream searches here.

## Previous Guarded News Trial (2026-09-10)

- User approved resuming the existing bounded trial after the caller audit.
  Fresh stamos/guarded-news-trial branch from clean main ac26c25. Preserve the
  frozen fixtures, candidate implementation, 10-second settling period and
  full 180-second cooldown. Stop at first degradation, without retrying queries.
- Preflight and VPN checks passed. First fixture (geothermal): 89 merged rows,
  three contributors, zero errors, 1.49s. Measured cold token-page HTTP returned
  200 in 0.41s. Score-only order replaced one top-five member with a relevant
  dated recent item; within-31-day metadata count 0 -> 1. One healthy sample is
  not enough to deploy or claim general relevance gains.
- Second fixture (coral): token-cache miss, token-page HTTP 200 in 0.25s, but
  DDG News timed out at the six-second search budget. Partial 45 rows from
  Brave/Reuters; ranking comparison skipped. Stopped immediately: remaining
  two Greek fixtures unqueried, no failed-query retry/cache reset/exit change.
- Neither token-page fetch needed more than two seconds, so this trial provides
  no evidence that raising its limit helps. HTTP 200 alone does not prove a
  usable parsed token; no token value/parse flag or downstream HTTP trace was
  captured. The second timeout happened after the token-page HTTP returned,
  not while waiting for that page. Do not increase global budgets as a fix.
- Brave News supplied no standard time/datetime markup in the 44/37 observed
  news nodes; this does not prove its whole response lacks dates. Source review
  and a synthetic in-memory probe also confirm cross-type duplicate merging can
  add engine attribution without copying an available publication date. This
  separate metadata-loss path needs a scoped fix/test; not every missing date
  is attributed to it. No result payloads or tokens persisted.
- Retain production unchanged: no timeout/ranking/date patch deployed. Full
  validator ran after the live trial (no competing validation Docker workload):
  32 benchmark + 12 candidate tests, 14 negative Compose cases and native
  privacy/offline-egress/recovery all passed. Builds N/A (no managed contexts).
  Additional pure in-memory merge probe passed. Final ops passed, three healthy
  services, localhost 8085 and VPN-only DNS/egress; disposable candidate removed.
- Detailed aggregate results/rubric grades in ISOLATED_NEWS_CANDIDATE.md. First
  two fixtures are now observed regression cases; Greek two remain unseen.
  No reboot, live VPN-stop or browser automation performed. No release applies
  to this experimental evaluation/documentation scope. This report accompanies
  the reviewed commit/push, main merge and completed-branch cleanup; continue
  future work from updated main on a new scoped branch.

## Previous Caller Metadata Audit (2026-09-10)

- User approved bounded caller/connection metadata diagnosis, not process
  termination, gateway interruption, packet capture or request logging. Fresh
  stamos/search-caller-audit branch from clean main 340307a.
- Initial 60-second Windows sample: 104 TCP snapshots, no matching client
  connections to loopback 8085. A 90-second search-namespace sample: 862
  snapshots, five distinct loopback TIME_WAIT sockets. Actual Docker health
  commands request root only every 30 seconds, not /search. Socket observations
  are consistent with health traffic, not proof of request contents.
- Only expected containers are on AnonExplo's three networks. Windows listener
  belongs to com.docker.backend; live nginx targets search-vpn:8080 and SearXNG
  shares that VPN namespace. Host proxy-bypassed and in-container error counts
  agree. No additional internal engine checker/scheduler found in this build.
- Selected engine error history stayed unchanged across a 40-second read-only
  comparison AND the final 180-second correlation window. The latter sampled
  310 TCP tables and saw one PID-0 TIME_WAIT socket, consistent with the audit's
  preceding local stats read but not attributable to any application. No live
  client was identified on loopback 8085 or the two resolved Docker 8080 targets.
- No background caller is established. Earlier changing statistics did not
  justify assuming a specific app or user activity. Sampling cannot reconstruct
  the past or exclude very short/unobserved connections; no retrospective request
  logs exist to attribute those changes. Do not mislabel PID 0 as an Idle caller.
- No search queries, history, command lines or packet contents collected; no
  persistent request logs or production changes. Only aggregate findings will
  be committed. Full validator passed: 32 benchmark tests, 12 candidate tests,
  14 negative Compose cases, native privacy/offline-egress/recovery checks.
  No managed image builds apply; temporary validation resources cleaned up.
- Outcome: currently quiet, no process to stop based on evidence. Diagnosis
  complete with an explicit attribution limit; no software fix or live candidate
  trial was authorized/performed in this metadata-only scope. Recommend resuming
  the existing guarded trial, not repeated quiet-window/caller investigations.
- Final production ops passed with the same three healthy services, 8085 and
  VPN-only DNS/egress. Only these audit documents changed; no deployment,
  installer/release, reboot or live VPN-stop drill applies.
- Git closeout was initially blocked by the automatic safety reviewer: the
  combined commit/push command was rejected before execution because the remote
  had not been verified for transmitting project/security notes. Read-only Git
  config confirms https://github.com/StamosArhon/AnonExplo.git, without embedded
  credentials. GitHub CLI is unavailable, so private visibility was not verified
  here. Audit commit 5b4b34c was retained locally. The user subsequently explicitly
  approved pushing these notes to the existing repository and finishing the
  merge. This closeout records that approval and accompanies the reviewed
  push/main merge/local and remote branch cleanup. The full validator already
  passed for this audit; this follow-up changes documentation only and uses
  whitespace/diff review, without rerunning Docker tests or production probes.

## Previous Quiet-Window Trial (2026-09-10)

- User confirmed a roughly five-minute quiet window and authorized the bounded
  live candidate evaluation. Fresh stamos/news-quiet-window-trial branch from
  clean main b65041a; use the existing frozen fixtures and candidate unchanged.
- First quiet-window preflight again detected differing error snapshots and
  sent no candidate queries. Safe diagnosis found one SearXNG worker, six
  matching back-to-back sanitized snapshots and no currently established host
  client connection to 8085. Native counters are cumulative, not time-decayed.
  These checks do not identify who sent earlier queries or prove inactivity.
- Added a ten-second settling interval before the error-history baseline for
  requests already in flight at confirmation (pinned max engine budget 8s).
  The full subsequent 180-second cooldown and strict comparison are unchanged.
  Pending requests are a possible cause, not an established explanation. One
  additional manual preflight also stopped on changed error history. The
  settling change did NOT solve the blocker. No provider query was retried.
- No production restart, provider change, cache/ban reset, key/exit change or
  browser edit. Both preflights sent zero candidate queries; all four frozen
  fixtures remain unqueried. No token/ranking improvement has been demonstrated.
- Full validator passed before and after the small settling change: 32 benchmark
  tests, 12 pinned candidate tests, 14 negative Compose cases, native privacy,
  offline egress and recovery. Image build N/A (no contexts). Final production
  ops passed: same three healthy services, 8085, VPN-only DNS/egress.
- Retain the settling interval as preflight hygiene, not a search fix. Stop
  further preflight attempts pending diagnosis of the changing error history.
  Next scope: bounded caller/connection metadata investigation without queries,
  browser history, command-line contents or persistent request logging. Ask
  before any gateway interruption or tracing that collects request content.
- Production config/Compose diff is empty. No candidate deployment, live
  kill-switch/reboot/browser drill or release. The live evaluation remains
  explicitly blocked, not passed.
- Implementation/report 6c72467 pushed and reviewed against main; whitespace
  checks passed. This documentation closeout accompanies the fast-forward main
  merge and local/remote branch cleanup. No remote blocker; next investigation
  starts from updated main on a fresh branch. Do not claim the search fix shipped.

## Previous Isolated News Candidate Scope (2026-09-10)

- User approved the isolated adapter/ranking experiment. Fresh branch
  stamos/isolated-news-adapter from clean main cb3e9ed.
- Candidate is an unprivileged, read-only, disposable pinned-image process:
  no HTTP listener, ports, production cache, secrets or config writes. Offline
  tests use network=none; explicit live trial shares only the existing VPN
  namespace and resolver. Native in-process Flask search uses three existing
  News adapters, no added recipients or fetched article pages.
- Freeze four new EN/EL public fixtures before live evaluation. Change only
  the inner token budget 2 -> 4 seconds; retain native six-second engine
  deadline, parsing, cache semantics, filters and suspension behavior. Candidate
  News order uses native scores before layout grouping, leaving metadata intact.
- Guard exact upstream source hashes. Log only bounded stage timings/status,
  cold-cache boolean and aggregates; optional top-five snippet review. No raw
  adapter exceptions, tokens, pages or trace files. Stop on first degradation;
  never recreate the candidate as a retry/cooldown bypass.
- Offline implementation passed 12 new pinned-source tests plus native app
  initialization, 32 existing benchmark tests, 14 negative Compose cases and
  the full privacy/offline-egress/recovery validator. Early offline-only harness
  failures (PYTHONPATH and disabled Brave network dependency) were fixed before
  any live query. Image builds N/A: still no managed build contexts.
- Live preflight waited 180 seconds then refused to launch because production
  error history changed. Read-only follow-up found three DDG News error contexts,
  previously two; same-snapshot serialization compared equal. No candidate
  query was sent, and all four fixtures remain unseen. Asked the user for a
  roughly five-minute quiet window; no automatic reattempt or new provider.
- Native aggregate errors now show timeouts in both fetch_vqd and the actual
  request stage. Token failure is observed, but the proposed fix is not proven;
  don't imply every DDG error has the same cause. Full details and limitations
  are in ISOLATED_NEWS_CANDIDATE.md.
- Production unchanged. Candidate tools are safe for offline use; deployment
  awaits healthy cold-query results and topicality evidence. No release applies
  to this intentionally isolated experiment. Final full validator passed again;
  live ops passed with three healthy services, unchanged 8085 and VPN routing.
  Production config/Compose diff is empty. No browser automation, live VPN-stop
  or reboot/sleep drill was run. Offline candidate containers and validation
  project cleaned up; user data/cache/images remain untouched.
- Implementation 2f0cc98 was committed and pushed. Reviewed branch against main:
  only experiment tools, validator integration and docs; whitespace checks pass,
  no secrets tracked. This closeout accompanies the fast-forward main merge and
  local/remote branch cleanup. Resume from updated main on a fresh scope branch.
  Offline preparation is complete; live evaluation is explicitly deferred, not
  claimed passed. No remote blocker remains.

## Previous Holdout And News Diagnosis Scope (2026-09-10)

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
3. Date repair and manifest-identity/build-isolation fixes are complete. DDG
   diagnostics remain retired after their stop conditions. Offline review now
   reproduces misleading counters during a controlled TLS stall, without proving
   the live root cause. Upstream review and 0.16.3 offline comparison are now
   complete: same failure-counter behaviour, so no upgrade deployed. Keep the
   reproducible tests for a future relevant upstream fix; do not repeatedly
   probe providers or upgrade simply because a newer version exists.
   Later DDG web commit 765a999 is a distinct candidate, not a News timeout fix:
   its guarded offline executor and synthetic adapter tests are now implemented.
   Next integrate/test the exact native processor and real transport offline,
   including option forwarding, session cookies, redirects, cancellation and
   native cooldown/error mapping, before deciding on any live web trial. Keep
   Startpage inactive/disabled; do not adopt its new challenge handling by
   incidental image upgrade.
   Require healthy holdout/topicality evidence before any ranking deployment.
   Media/models/reboot drills remain separate.

## Continuity

Read AGENTS.md, this roadmap, INSTRUCTIONS_AND_NOTES.md, ARCHITECTURE.md,
and SECURITY_PRIVACY.md. Prior evidence is preserved in
LEGACY_IMPLEMENTATION_ROADMAP.md; its LLM roadmap and fallback advice are superseded.

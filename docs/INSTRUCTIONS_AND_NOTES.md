# Instructions And Notes

## Current Product

- AnonExplo is SearXNG at localhost:8085. Brave uses /search?q=%s directly.
- The legacy UI, orchestrator, fetcher, model runtime and provisioning scripts
  are removed, not profile-gated. Recover historical code from Git if needed.
- Future local result refinement can run headlessly. It needs its own relevance/
  latency evaluation and internal-only model boundary, not a new interface.
- Only three production services: host-gateway, search-provider and search-vpn.
- Configure browser engines/language in configs/searxng/settings.yml and native
  preferences. Old SEARCH_/MODEL_/GROUNDING_/FETCH_ .env keys are inert; existing
  .env files are preserved rather than rewriting secrets during migration.

## Privacy And Operations

- Bind only the gateway search port to 127.0.0.1. No legacy app ports.
- Base Compose search is internal-only/offline. The Proton overlay supplies the
  sole supported search egress; startup never falls back to direct networking.
- Preserve VPN-local DNS, firewall, dedicated read-only WireGuard credential,
  dropped capabilities, read-only roots and localhost control API.
- Missing credentials mean stop. After VPN replacement use
  start-proton-search.ps1 -Recreate so namespace clients are recreated.
- Native privacy locks keep autocomplete/favicons off, image proxy on, query
  titles off. Engine/language/category/SafeSearch choices remain available.
- No-store/no-referrer and quiet logs are not browser-history erasure or a
  guarantee that upstream engines do not retain queries. Result clicks are direct.
- Keep upstream cooldowns. Never clear bans, rotate VPN exits or poll providers
  automatically to conceal errors. No telemetry, query database or remote NLP.
- Use synthetic manual benchmarks, never private browser history/cookies.
- Expanded benchmark suites: informational, news (Anytime), news-month. Only
  explicit -ReviewTop5 displays bounded public-fixture snippets; no transcripts
  or result payloads in Git. Record manual snippet-level grades, not correctness.
- Engine and category selectors are unioned by SearXNG: diagnostics MUST send
  one or the other, never both. Verify local catalogue eligibility first.
- Unsupported time filters exclude engines. In this build filtered News leaves
  only Reuters; do not fake support or silently discard a user's filter.
- Preserve Bing weight 0.35 pending new evidence; engine remains available.
  Manual benchmark pace is 15 seconds, stop on degradation. Wait out cooldowns
  before any necessary settings restart; never restart to clear a ban.
- Holdout fixtures are frozen before evaluation; after inspection they become
  regression cases. Do not tune on them and keep calling them unseen validation.
- default-audit is a four-fixture official-destination coverage check, not general
  relevance. Top-five credited/sole-credit counts describe one merged response,
  not marginal engine quality or the effect of removing an engine. See
  DEFAULT_ENGINE_COVERAGE.md for evaluation status before any use.
- CompareScoreOrder replays one response in memory only; no production reranking.
  Degraded samples are excluded. StartAt is deliberate manual suffix selection,
  not permission to retry failing providers or auto-resume after errors.
- News has native thumbnail/template grouping after scoring, missing Brave News
  dates and a separate hard-coded DuckDuckGo token timeout. Read
  HOLDOUT_AND_NEWS_RANKING.md before any adapter/ranking patch; global timeout
  increases and new providers do not directly address these mechanisms.
- Isolated candidate tools are experiment-only, never production imports. Read
  ISOLATED_NEWS_CANDIDATE.md before using test-news-candidate.ps1 -Live. Its
  process does not share native suspension state: respect preceding cooldowns,
  avoid concurrent searches, stop on degradation and never recreate as a retry.
  Default invocation is network-disabled and sends no queries. Exact source
  fingerprints must be reviewed, not blindly updated on an image change.
- The metadata audit found no attributable caller. The subsequent approved
  guarded trial finally passed preflight: one healthy fixture, then DDG timeout
  after its token-page HTTP returned quickly. Stopped; no production changes.
  Do not rerun the failed candidate suite or claim a longer token timeout helps.
  Its first two fixtures are observed, two Greek fixtures remain unseen.
- Cross-type MainResult/LegacyResult deduplication can lose an available date
  while preserving both engine names. Same-type merges also leave explicit None
  unchanged in this pin. The guarded images/searxng repair fills only a missing
  date from an incoming datetime, preserves existing dates and updates pubdate.
  Native macro item lookup fixes LegacyResult's shadowed pubdate attribute.
  Read PUBLICATION_DATE_REPAIR.md before image updates or rollback.
- SEARXNG_IMAGE is intentionally inert; local tag anonexplo/searxng:date-merge-v1
  comes from a pinned base and two source fingerprints. Validate before deploying;
  never blindly update guards. No source mounting or runtime monkeypatching.
- The historical News candidate's -Live mode now refuses immediately. Its failed
  suite must not be retried; original-image offline tests remain characterization.
  A new DDG diagnostic needs its own scope, fixtures and compatibility review.
- The subsequent DDG-only trace stopped on its first fresh fixture: token HTTP
  timed out in 2.002s, before parsing or the downstream News request. This does
  not explain the earlier post-token-page failure or prove a DNS/TLS/root cause.
  Read DDG_REQUEST_DIAGNOSIS.md. Its -Live mode is now refused; do not rerun failed
  fixtures. Any new transport observation needs a fresh scoped decision, no
  payload logging, native timeout/retry semantics intact, and normal cooldowns.
- The approved transport batch observed one healthy DDG News fixture, then another
  cold-token HTTP timeout at 2s. Counters do not prove the network/root cause;
  see DDG_TRANSPORT_TIMINGS.md. No production search change was justified. Both
  diagnostic fixture sets are retired from PowerShell -Live; do not bypass that
  guard with the Python runner. -Transport offline checks preserve source guards,
  numeric-only capture and native argument/return/exception behavior.
- -TimeoutSemantics runs only mocked caller/retry tests and container-loopback
  transfers under network=none. Read OFFLINE_TIMEOUT_SEMANTICS.md: the pinned
  TLS-stall path reports zero TCP completion and nonzero first-byte time despite
  confirmed TCP acceptance and no server response. Do not infer live network
  phases from those counters alone. Caller timeout does not explicitly cancel
  its future; this is not proof of the observed transport timeout's cause.
- Read UPSTREAM_TRANSPORT_REVIEW.md before client updates. The reviewed 0.16.3
  offline candidate reproduces the same counters and is not deployed. Provision
  its exact glibc wheel separately; -TimeoutSemantics -ClientCandidate and optional
  validate.ps1 -TransportCandidate never download at runtime or get VPN access.
  Default guards accept only production sources. Candidate hashes are explicit,
  not a bypass; executable /candidate tmpfs exists only in that offline container.
- NEW_DDG_ADAPTER_REVIEW.md covers later upstream DDG web/Startpage changes.
  They are not a verified fix for the DDG News token timeout. Keep web opt-in
  and do not activate new challenge flows through a broad image update. Any web
  candidate needs explicit allowed-origin/redirect and bounded parsing/budget
  review for response-derived follow-up URLs before a live trial.

- GUARDED_DDG_WEB_CANDIDATE.md documents the implemented offline web executor.
  Provision its exact source explicitly; test-ddg-web-candidate.ps1 and optional
  validate.ps1 -WebCandidate are network-disabled and -Live refuses. It wraps
  upstream request/response with mocks, not the native online processor. Never
  import it into production or infer real behaviour from those original mocks.
- DDG_WEB_NATIVE_INTEGRATION.md records the subsequent native processor/client
  TLS tests. -Integration stays network=none; validate.ps1 -WebCandidate runs both
  mock and integration suites. Test-only CA/DNS overrides must never reach a live
  image. The candidate preserves native suspension/error mapping, restricts
  unsupported filters, caps decompressed bodies and cancels overdue transport.
  A future bounded trial still needs fresh fixtures/cooldown preflight: isolated
  process state does not inherit production's suspension history. -Live refuses.
- The separate test-ddg-web-trial.ps1 is the completed one-shot web trial, not a
  bypass of older live guards. It defaults to offline startup; its live run required
  quiet/cooldown and VPN preflight, frozen fixture hashes and an unused atomic
  marker. Its first preflight stopped on changed stats before dispatch. The
  user-confirmed second preflight passed: one healthy query, then first-page HTTP
  timeout at 2s. Trial now retired in both PowerShell and Python live entrypoints;
  never erase its marker, reset suspension, retry observed queries or send its
  remaining Greek fixture. Read DDG_WEB_GUARDED_TRIAL.md. No deployment justified.

## Startup And Migration

- setup-browser-search.ps1 -SkipBrowserConfiguration refreshes hidden startup
  without touching browser profiles or needing Node for normal startup.
- Browser configuration remains available separately through the setup script;
  only invoke it deliberately, with browsers closed. Do not force-close sessions.
- remove-legacy-components.ps1 starts/verifies the reduced deployment, removes
  only old service containers identified by project/service labels, and retires
  the exact old redirector task/process. It leaves images, volumes and data.
- If Windows denies deleting an admin-owned task, its exact user-owned launcher
  is replaced with a backed-up no-op. Report the remaining task entry honestly.
- Historical helper directory name search-fallback is retained to avoid breaking
  existing startup-task actions; it does not imply a running fallback service.

## Validation And Workflow

- RERANKER_SHADOW_TEST.md scopes the requested one-shot real-result comparison.
  Use only frozen public fixtures and ignored local preferences; stdio to a
  network-none model, metrics/grades only on disk. No production integration.

- LOCAL_RERANKER_TRIAL.md is an explicitly approved separate model experiment.
  Provision downloads only in the provisioning step; inference is network=none,
  local-files-only, no remote code, no production mount or endpoint. Keep private
  preferred domains out of Git. Model scores are not calibrated probabilities.

- SEARCH_QUALITY_DECISION.md replaces incremental tuning as the current quality
  scope: frozen development/holdout split, two fixed same-response policies,
  explicit snippet grades, deployment gates and no retry/tuning loop on failure.
  Closed with DO NOT DEPLOY after question 12 degraded: 11 graded, 20 unsent,
  no holdout evaluation. Both live entrypoints are retired. Preserve its marker
  and metrics-only grades; no new parameter trial or automatic resume. Never
  persist payloads. Future structural retrieval work requires a new decision.

- Branch per scope: stamos/<name>; update roadmap, validate, review, commit/push,
  merge only ready work, delete completed branch. No desktop release applies.
- Bundle approved work into 3-4 steps; continue normal branches without asking
  between them. Report at batch completion; interrupt only for meaningful blockers,
  privacy/security tradeoffs, cost or scope expansion. Preserve scoped branches.
- validate.ps1 uses project anonexplo-validation, port 18085, and tmpfs cache.
  It neither mounts the VPN credential nor shares the live search cache.
- Validate Compose policy including negative fixtures, script syntax, offline
  helper/benchmark tests, native UI/settings/headers and outage/recovery.
- Compose build now builds/tests the small SearXNG date repair, with network-none
  RUN steps and a data-excluding context. No legacy application build is restored.
  Runtime validation repeats date tests plus existing ranking/privacy checks.
- ops-check.ps1 verifies the three-service live topology and VPN isolation.
- ops-check compares exact runtime platform manifests, not the OCI index that
  changes with provenance. Missing descriptor support fails closed; update Docker
  deliberately, never fall back to tag-only equality. Offline validation builds
  use their own tag and verify the production tag is untouched. Build production
  explicitly after candidate validation when deliberately deploying an update.

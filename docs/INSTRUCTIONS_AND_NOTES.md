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

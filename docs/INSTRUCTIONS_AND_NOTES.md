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
- validate.ps1 uses project anonexplo-validation, port 18085, and tmpfs cache.
  It neither mounts the VPN credential nor shares the live search cache.
- Validate Compose policy including negative fixtures, script syntax, offline
  helper/benchmark tests, native UI/settings/headers and outage/recovery.
- No custom image build contexts remain. Compose build is checked but reports
  no services to build; do not pretend deleted application tests/builds ran.
- ops-check.ps1 verifies the three-service live topology and VPN isolation.

# AnonExplo

AnonExplo tunes and operates **SearXNG as a private browser search engine**.
Its UI is SearXNG itself, not a chatbot. No LLM is needed for browser search.

## Use On This PC

- Search UI: [localhost SearXNG](http://127.0.0.1:8085).
- Brave search template: `http://127.0.0.1:8085/search?q=%s`.
- [Preferences](http://127.0.0.1:8085/preferences): engines, language, categories
  and appearance. Engine/language cookies can override instance defaults.
- Use `:el` or `:en` in a query for an explicit language choice. No hidden
  translation, rewriting or multi-query expansion occurs in this browser path.

Only search traffic uses the per-PC Proton WireGuard tunnel. The rest of the PC
and websites opened from result links use their normal routes. Search providers
still see the query; a VPN is not a guarantee against provider retention.

## Start And Check

The dedicated Proton credential is already installed on this PC. Do not replace
it or print its contents. From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-proton-search.ps1
powershell -ExecutionPolicy Bypass -File scripts/check-proton-search.ps1
```

After VPN namespace replacement, use `start-proton-search.ps1 -Recreate`.
For another PC, bootstrap and import a separate WireGuard credential as described
in [operations](docs/OPERATIONS_AND_MAINTENANCE.md). Do not start direct-egress
search as an automatic fallback when the VPN is unavailable.

## Tuning And Privacy

`configs/searxng/settings.yml` controls native browser search. The tested general
defaults are Brave, Bing and Yahoo plus Wikipedia information boxes. News and
Science have separate curated sources. Other providers remain optional after
observed empty, intermittent, denied or CAPTCHA responses; see
[engine coverage](docs/SEARCH_ENGINE_COVERAGE.md).

Bing remains available with reduced ranking influence after off-topic matches
in informational tests. For broad News coverage, use **Anytime**: in this build,
Past month excludes Brave News and DuckDuckGo News, leaving only Reuters.

Autocomplete and remote favicon resolution are locked off; query titles are
hidden and SearXNG images are proxied. The gateway sends no-store/no-referrer,
does not write search request errors or buffer result bodies to temporary files,
and fails locally when unavailable. Brave GET query URLs can still appear in
browser history/sync; these safeguards do not erase browser history.

## Test

```powershell
# Isolated validation, offline tests and local smoke; no live search fixtures.
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
# Manual public synthetic searches through the VPN, not browser history.
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1
# Compare explicit query languages against the browser-locale baseline.
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -LanguageMode explicit
# Broader questions; explicit review displays bounded public-fixture snippets.
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite informational -ReviewTop5
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite news
# Fixed independent follow-up cases and same-response ranking diagnostics:
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite holdout
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite news-holdout -CompareScoreOrder
```

The benchmark reports rank/domain/latency proxies; informational/news relevance
requires manual rubric grading. Default output has no result text. Expanded
suites report eligible engines and unsupported time filters. Runs are paced at
15 seconds and stop on errors or empty results, never bypassing cooldowns.
See [browser integration](docs/BROWSER_SEARCH_INTEGRATION.md).
The [holdout/News investigation](docs/HOLDOUT_AND_NEWS_RANKING.md) explains
layout grouping, missing news dates and the adapter's separate token timeout.
No live ranking behavior is changed by the diagnostic replay.
The [isolated candidate trial](docs/ISOLATED_NEWS_CANDIDATE.md) tests a bounded
token timeout and News score ordering; its live mode is now retired after a
failed trial. It did not justify a timeout/ranking deployment.

The [publication-date repair](docs/PUBLICATION_DATE_REPAIR.md) preserves a date
supplied by another engine when duplicate results merge, including native HTML
date markup. It does not invent missing dates, change ranking or cure timeouts.

## Removed Legacy Components

Only `host-gateway`, `search-provider` and `search-vpn` remain. The old chatbot
UI, backend, fetcher, model runtime/provisioner and redirector have been removed.
Ports for the old UI/API are no longer published. Source is recoverable from
Git; credentials, browser storage, search cache and cached Docker images remain.

For an older installation, refresh startup with
`setup-browser-search.ps1 -SkipBrowserConfiguration -NoStartNow`, then run
`remove-legacy-components.ps1` and `ops-check.ps1`. The base Compose file is
offline/internal-only; startup requires the VPN overlay, never direct fallback.

SearXNG uses a small local repair image built from a digest-pinned upstream base;
gateway and VPN images remain upstream digest pins. Run the full validator
before deployment; use `start-proton-search.ps1 -Build` for the initial build.
Any future local model can refine results
headlessly, but none is needed or installed now.

[Roadmap](docs/IMPLEMENTATION_ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Privacy](docs/SECURITY_PRIVACY.md) · [Historical workbench](docs/LEGACY_LLM_WORKBENCH.md)

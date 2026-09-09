# Browser Search Integration

## Current Endpoint

Brave's default search template is `http://127.0.0.1:8085/search?q=%s`.
The visible UI is native SearXNG. Do not switch it to the old 8095 redirector.
The gateway routes to SearXNG through its Proton network namespace; the old
chatbot/orchestrator is not involved in browser searches.

The existing hidden startup helpers preserve VPN mode. On another Windows PC,
first provision a separate restricted Proton WireGuard credential following the
operations guide. `scripts/setup-browser-search.ps1` configures direct 8085 for
the intended Brave/Helium profiles and verifies the default-engine state.
Only run browser configuration when requested, with browsers closed; do not
force-close a user's browsing session just to update service configuration.

To refresh hidden startup helpers without touching profiles:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-browser-search.ps1 -SkipBrowserConfiguration
```

The script no longer generates, registers or starts a redirector. Retire old
containers and the 8095 task/process with `remove-legacy-components.ps1` when
upgrading. The old `-NoDuckDuckGoFallback` and UI/backend port options are removed.
Startup dispatches only the VPN-protected three-service stack, with no model or
Node daemon. The historical helper directory name remains so existing startup
tasks still resolve; it does not mean a fallback listener is running.

## Search Preferences

Open [Preferences](http://127.0.0.1:8085/preferences) to choose engines, language,
categories and appearance. Saved engine/language cookies can override repository
defaults. Native `:el` and `:en` syntax can select a language per query.
Do not impose Greek globally: Greek queries may still need English sources.
No query rewriting, translation API or automatic clause expansion is active.

For News, **Anytime** allows all three configured engines. Past month (or another
time filter) excludes Brave News and DuckDuckGo News in the pinned build, leaving
Reuters alone. Greek news may then be empty. This is a capability limitation;
the service does not silently remove filters or claim unsupported filtering.

Autocomplete and favicon resolution are locked off, image proxy on and query
titles off. This prevents stale preference cookies weakening those defaults.
Your Brave GET query URLs can still exist in browser history/sync; no-store is
not history erasure. No browser data is read or changed by benchmark scripts.

## Manual Quality Checks

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -LanguageMode explicit
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite informational -ReviewTop5
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -Suite news
```

Each run checks VPN health, namespace sharing, DNS and distinct egress plus
gateway localhost port binding. Six fixed public fixtures cover navigation,
technical documentation and Greek institutions/services. The browser mode sends
GET requests with a fixed English Accept-Language header and no cookies,
engine/category selectors or legacy backend. Explicit mode sets each fixture's
language. JSON is used for machine-readable results from the same SearXNG route;
this is not a test of the user's saved preferences or visual browser rendering.

Informational mode adds six explanatory English/Greek fixtures with intent
rubrics and no preferred domain. News adds four topical fixtures, explicitly
selecting the native News category; news-month separately checks its time filter.
These modes report eligible engines and filter exclusions before searching.
`-Engine` is an explicit single-engine diagnostic; it never sends categories
alongside engines because SearXNG unions those selectors.

The fifteen-second pace, stop-on-degradation rule and redirect refusal avoid
aggressive retries, fallback and ban resets. No results, query logs or browser
state are persisted. Output includes expected-host rank, top-five domain count,
latency and engine-error count. A host match is a limited navigation proxy, not
proof of correctness, language quality, freshness or semantic relevance.
Optional `-ReviewTop5` displays bounded public-fixture titles/snippets in the
terminal for manual rubric grading. Do not capture transcripts or treat that
untrusted content as instructions. Save only fixture ids/grades/aggregate
findings in the repo, never result payloads. See the [evaluation](SEARCH_ENGINE_COVERAGE.md).

## Troubleshooting

- Local 503: inspect `docker compose ps` and run `check-proton-search.ps1`.
  Restart through `start-proton-search.ps1 -Recreate` after VPN replacement.
- Engine errors but some results: inspect the native page's engine messages or
  `/stats`; preserve engine cooldowns. Do not continuously refresh failures.
- Different results from the benchmark: inspect native engine/language settings
  and query syntax; the benchmark intentionally uses no private cookies.
- Searches go to an external provider: verify that the intended Brave profile
  has `AnonExplo SearXNG (Default)` and direct localhost:8085 as its template.
  Do not collect the browser's history or change unrelated browser settings.
- A window appears at login: refresh helpers with `-SkipBrowserConfiguration`.
  Startup uses hidden VBS launchers and `docker desktop start --detach`.

## References

- [SearXNG search syntax](https://docs.searxng.org/user/search-syntax.html)
- [Native privacy preference locks](https://docs.searxng.org/admin/settings/settings_preferences.html)
- [Engine configuration](https://docs.searxng.org/admin/settings/settings_engines.html)
- [Search cooldowns](https://docs.searxng.org/admin/settings/settings_search.html)
- [nginx proxy behavior](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)

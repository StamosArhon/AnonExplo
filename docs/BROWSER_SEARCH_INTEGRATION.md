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

The script still generates/registers the compatibility redirector at 8095 for
older local clients, but external fallback is disabled unconditionally. The
old `-NoDuckDuckGoFallback` switch is retained as a no-op compatibility option.
Removing the redundant helper and legacy app startup dependencies is planned
as a separate search-only-deployment milestone.

## Search Preferences

Open [Preferences](http://127.0.0.1:8085/preferences) to choose engines, language,
categories and appearance. Saved engine/language cookies can override repository
defaults. Native `:el` and `:en` syntax can select a language per query.
Do not impose Greek globally: Greek queries may still need English sources.
No query rewriting, translation API or automatic clause expansion is active.

Autocomplete and favicon resolution are locked off, image proxy on and query
titles off. This prevents stale preference cookies weakening those defaults.
Your Brave GET query URLs can still exist in browser history/sync; no-store is
not history erasure. No browser data is read or changed by benchmark scripts.

## Manual Quality Checks

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1
powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1 -LanguageMode explicit
```

Each run checks VPN health, namespace sharing, DNS and distinct egress plus
gateway localhost port binding. Six fixed public fixtures cover navigation,
technical documentation and Greek institutions/services. The browser mode sends
GET requests with a fixed English Accept-Language header and no cookies,
engine/category selectors or legacy backend. Explicit mode sets each fixture's
language. JSON is used for machine-readable results from the same SearXNG route;
this is not a test of the user's saved preferences or visual browser rendering.

The five-second pace, stop-on-degradation rule and redirect refusal avoid
aggressive retries, fallback and ban resets. No results, query logs or browser
state are persisted. Output includes expected-host rank, top-five domain count,
latency and engine-error count. A host match is a limited navigation proxy, not
proof of correctness, language quality, freshness or semantic relevance.

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

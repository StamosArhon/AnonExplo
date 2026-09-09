# Search engine coverage: VPN audit, 2026-09-09

## Native Browser Baseline (2026-09-10)

The product is native SearXNG at localhost:8085, not the legacy backend.
`test-browser-search.ps1` measures instance-default GET search without cookies
or engine/category overrides, using six fixed public English/Greek fixtures.
Browser-locale mode: 6/6 expected sites rank 1, no errors, mean 1.18s.
Explicit-language mode: 6/6 rank 1, no errors, mean 1.19s. All queries had three
contributing web engines. No engine weights or language defaults were changed.
These are navigation proxies and sequential observations, not a broad relevance
score, independent-index proof or controlled performance comparison. The suite
does not inspect Brave's saved preferences/history. Stop on degradation and
keep native suspensions; do not schedule tests or rotate exits automatically.

## Selected profile

- General web: Brave, Bing, Yahoo; Wikipedia supplies info boxes.
- News: Brave News, DuckDuckGo News, Reuters.
- Science: arXiv, PubMed, Crossref.
- Opt-in, disabled by default: DuckDuckGo web, Google web/news, Startpage,
  Mojeek, Qwant. Disabled means available in Preferences, not a hidden fallback.

Only SearXNG traffic uses the existing Switzerland Proton tunnel. No VPN exit
rotation, CAPTCHA bypass, paid search API, search account, or new external
redirect was introduced. More recipients do not imply independent indexes,
better results for every query, or provider-side non-retention. Fetcher traffic
and clicked browser result pages still take their ordinary non-VPN route.

## Image comparison

The installed April build (`2026.4.11+9e08a6771`) was compared with the official
September build (`2026.9.8+3fdc6d753`) in a temporary container sharing the
existing VPN namespace, with no published ports, read-only config and resolver,
and ephemeral cache. The candidate never mounted Proton credentials.

Selected image:
`searxng/searxng:latest@sha256:3547509b419cd6a67333d6d68bd1ffad8d46d3669d82e7a7bd538f7b45827432`.
The tag is digest-pinned, not a floating automatic update.

Three synthetic public fixtures exercised English navigation, technical docs,
and a Greek museum search. Counts are parsed result rows, not estimates from
an engine's total-result counter. Expected-domain-in-top-five is a narrow
smoke metric, not a relevance benchmark. No real user history or result bodies
are stored in this report.

| Engine | April build / first probe | September candidate | Decision |
| --- | --- | --- | --- |
| Brave | 20/20/21 rows; expected host top-five in 2/3 | Cold timeout once; repeat 20/20/21, host top-five 3/3 | Retain |
| Bing | 10 rows per fixture; host top-five 2/3 | 10 per fixture; host top-five 2/3 | Retain |
| Yahoo | HTTP protocol error | 7 per fixture; host top-five 3/3 | Enable |
| DuckDuckGo web | Access denied | First request 10 rows, subsequent probes timed out | Opt-in only |
| Google web | Empty on all three fixtures, no explicit error | Empty on navigation probe | Opt-in only |
| Startpage | CAPTCHA | Not retried | Opt-in only |
| Mojeek / Qwant | Access denied | Not retried | Opt-in only |

One synthetic news probe returned Brave News 50, DuckDuckGo News 30, and
Reuters 20 rows. Google News returned CAPTCHA and was removed from defaults.
One synthetic research probe per engine returned arXiv 10, PubMed 20, and
Crossref 19 rows; Crossref was previously present but disabled.

Tests were paced and engines with reported errors were not hammered or had
their suspensions cleared. Cold/transient failures remain possible. This is a
snapshot on one exit, not proof of zero errors or long-term reliability.

After deployment, the manual three-engine x three-fixture suite completed all
nine requests without reported errors and with the expected host in the top
five for each. Browser defaults returned 27 combined Brave/Bing/Yahoo rows;
the backend returned its configured eight. The updated stack also passed an
actual VPN-stop/recovery test (direct HTTPS, direct DNS, and IPv6 blocked),
with all six services healthy afterward. Post-recovery search again returned
27 rows without reported errors; the browser redirector returned only a local
SearXNG 302. The temporary candidate and its ephemeral data were removed.

Full isolated validation passed twice, including 52 backend and 19 fetcher
tests. The optional model-runtime probe was skipped because no GGUF is present.

## Selection and privacy correction

Live isolation tests and the pinned SearXNG `webadapter.parse_generic` code
showed that sending `engines=brave` together with `categories=general` also
queried Bing. SearXNG unions these selections. The backend now sends explicit
engines **without categories**, and only uses categories when the engine list
is empty. Adaptive ordinary/news filtering still applies to explicit engines.
Defaults now agree across Python settings, Compose, and `.env.example`.

Timeouts remain bounded at 5-8 seconds per engine with an 8-second SearXNG
maximum and a 20-second backend budget. Built-in suspension/backoff is not
disabled, error messages are not hidden, and autocomplete remains off.
No engine-weight changes were justified by this small sample.

Existing browser SearXNG preference cookies may preserve old engine choices.
Review the local `/preferences` selections; do not delete browser history or
other browser state to apply these defaults. The backend selector is separate.

## Repeatable checks

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-search-coverage.ps1
# Explicit opt-in diagnostic for one loaded candidate (may fail):
powershell -ExecutionPolicy Bypass -File scripts/test-search-coverage.ps1 -Engines duckduckgo -Samples 1
```

This manual helper first verifies the running VPN, resolver, and distinct
egress. It uses synthetic fixtures only, POSTs to localhost, checks that no
unrequested engine contributed rows, prints aggregate metrics, and stops the
remaining samples for an engine after a reported failure. It does not save
queries, results, or IPs. Zero results without an error remain visible as zero.
Do not automatically rerun it or use private queries as committed fixtures.

`scripts/validate.ps1` separately checks builds, unit tests, script syntax,
Compose/VPN policies, localhost health, loaded category defaults, and that the
backend selectors name loaded engines. It does not issue upstream searches.

## Deployment and rollback

Existing machines need both `SEARCH_ENGINES` and `SEARXNG_IMAGE` refreshed from
`.env.example`; do not overwrite their whole `.env`. Preserve the VPN Compose
selection, ports, key file, and resolver. Rebuild the backend and recreate only
the affected services with the VPN overlay still selected:

```powershell
docker compose up -d --build --no-deps --force-recreate --wait search-provider backend host-gateway
powershell -ExecutionPolicy Bypass -File scripts/check-proton-search.ps1
```

For rollback, restore the pre-change tracked settings and backend image from
the preceding main revision through a reviewed branch; restore only the two
changed local search keys. The previous SearXNG digest was
`sha256:00b57726b3d732c11f874af964ce68c9e5c38c02d73040567603c0681f0b6007`.
Its selector was `brave,bing,wikipedia,duckduckgo news,google news,reuters`.
Do not remove the Proton overlay or use a direct-provider redirect as rollback.

References: [official container deployment](https://docs.searxng.org/admin/installation-docker),
[engine configuration and disabled-engine semantics](https://docs.searxng.org/admin/settings/settings_engines.html),
[search settings and suspension controls](https://docs.searxng.org/admin/settings/settings_search.html).

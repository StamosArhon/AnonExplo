# Browser preferred-source preview

**Current behavior:** the separately approved remembered/automatic v2 is documented
in [AUTOMATIC_PREFERRED_COVERAGE.md](AUTOMATIC_PREFERRED_COVERAGE.md). It supersedes
the v1 use/ranking/default and no-extra-query limits below. The remaining text
records the original v1 implementation and its validation, not current v2 behavior.

User-approved opt-in browser integration, not a claim of measured relevance gains.
The earlier synthetic model trial passed, while the separate shadow attempt
stopped on the first Brave error before real inference. Its unmerged branch and
retired fixtures remain untouched. This scope makes hands-on comparison possible.

## Use

Search normally at http://127.0.0.1:8085 using Brave or the native form. On a flat
default-template results page, click **Preferred sources: OFF** above the list.
It becomes ON after successful local evaluation. Toggle OFF to restore the exact
original order; toggle ON again reuses the same in-page result, without another
provider query or model call. Every new page starts OFF. No cookie/localStorage
or cross-page query/result cache is introduced. Grouped/media layouts are excluded.

Only the first 24 returned rows can move. Preferred sources must score >=0.8 on
the existing local multilingual model; a 15% native-score boost can move them at
most two places and cannot pass a result scoring >0.05 higher for relevance.
This is a conservative heuristic, NOT a guarantee of relevance or factual truth.
No retrieval of missing preferred sites, query rewriting or article fetching.
Partial provider responses can be compared as returned; native engine error
messages remain visible and this does not repair missing results.

Busy, unavailable, invalid or late inference retains native order. Browser
deadline 5s; server rejects outputs taking >4s; bounded inference already running
can finish after the UI has fallen back. At most one inference at a time, no
inference queue and at most eight local handler threads. No automatic retries.
Zero matching preferred sites skips model inference entirely. Status explicitly
distinguishes no preferred matches from no qualifying promotions.

## Isolation and deployment

Normal path remains Brave -> gateway:8085 -> VPN-isolated SearXNG -> providers.
Opt-in path: existing result titles/snippets/native scores/URLs and query ->
same-origin gateway POST -> Unix socket -> **network=none** model -> numeric order.
The model cannot fetch URLs or access a DNS resolver, VPN key, search cache,
browser storage or internet. Only the existing localhost port is published.
Gateway rejects cross-site/non-JSON/non-POST requests; no CORS permission added.
Query POST bodies stay in memory (64KiB gateway/server bound, no temp buffering).

Separate project `anonexplo-preview`, immutable already-provisioned CPU image
ID, read-only pinned/hash-verified model, read-only scripts and local preferences,
non-root, dropped capabilities, no-new-privileges, 12GiB/8CPU/256PID limits,
logs disabled and HF offline/telemetry locks. Startup verifies all seven artifacts;
no runtime dependency or weight downloads. Socket is in a 1MiB tmpfs volume
shared only with gateway. Shared volume contains a socket, never query files.
RAM/swap, host compromise and browser history remain outside erasure guarantees.

Native search image adds only guarded template score attributes and a same-origin
deferred script. No SearXNG request/engine/ranking logic is patched for preview.
Existing date-repair guards remain intact. Base/offline search still cannot egress.
Personal site list is `data/preferences/shadow-domains.json`, ignored by Git;
the name is retained for this PC, not an active shadow-test dependency.

Run `scripts/start-preview.ps1` after the gateway socket volume exists. The
separate container restarts with Docker unless deliberately stopped. Normal
search startup has no model dependency. Stop preview with:

```powershell
docker compose -f docker-compose.preview.yml stop reranker
```

For complete UI rollback, preserve and retag the deployment's
`anonexplo/searxng:before-preference-preview` image to the normal search tag and
recreate only search-provider after reviewing cooldowns. Gateway routes can remain
inert; no VPN recreation, cache/ban reset, browser profile changes or data deletion.
Use `deploy-preview.ps1` only after both validation scripts pass; it preserves a
rollback image, waits for quiet, promotes the exact validated image, compares manifests, replaces
only gateway/search, starts preview and verifies the unchanged VPN identity.

## Validation status

- Eight policy/input unit tests; existing relevance-gate tests unchanged.
- Executed actual browser JS against a minimal DOM: default off, reorder,
  unscored tail, exact restore, cached toggles, failure/malformed response and
  grouped-layout protection. No automated Brave session available; no relaunch.
- Three native template rendering/escaping/source-guard tests, both result types.
- Six actual Unix transport failure/busy/deadline/health tests with injected scores.
- Real network-none model/socket test: relevant synthetic source promoted,
  irrelevant preferred source not promoted, no-match bypass and malformed inputs.
  Two-pair measured inference 0.143s; not a 24-result latency or quality claim.
- Full validate.ps1 includes preview Compose policy and four negative cases.
  Small validation-only subnets 10.254.250.0/28 and 10.254.250.16/28 resolve the
  exhausted automatic pools on this PC. Existing networks/routes inspected first;
  no global Docker configuration or other project network changed/deleted.
- Full expanded validation passed: 99 host tests, 12 historical candidate tests,
  11 timeout tests, 13 date-repair tests, three preview render/build tests, DOM
  suite, 20 negative core Compose cases, four preview cases, identity guards,
  privacy/blocked egress and isolated outage/recovery. Model/transport tests passed.
- The first deployment command was rejected by the safety reviewer before execution:
  explicit approval requested for briefly replacing live search and gateway.
  No quiet window, live image build, rollback retag, container replacement or
  preview service startup ran in that attempt. The user subsequently explicitly
  approved replacement of the live search and gateway.
- Gateway include uses an optional glob so its existing bind-mounted config
  remains valid even in an older container without the new preview assets mount.
  The running gateway's `nginx -t` passes; all three live services remain healthy
  with unchanged uptimes. All 18 local preferred domains passed input validation.
- Approved deployment completed after a successful 180-second quiet/cooldown
  check. Initial artifact equality check stopped before container replacement:
  rebuilding with a different Compose project changed only image config labels,
  not filesystem layers. Fixed deployment to promote the exact validated artifact,
  retaining strict manifest equality rather than weakening the guard.
- Corrected a YAML healthcheck escape issue before model startup. The resolved
  Python health command is now compiled during policy validation/startup.
- Search/gateway replaced; VPN container identity unchanged. Three core services
  and the separate preview service healthy. Runtime model network=none, no
  published ports, read-only root, disabled logs, socket volume confirmed tmpfs.
  Rollback image retained as before-preference-preview.
- Deployed gateway smoke passed: JS asset, no-store/no-referrer, method/content/
  cross-site restrictions, real local promotion (two pairs 0.161s), irrelevant
  preferred result retained in native order. No URLs fetched or payload files.
- One fresh public synthetic HTML search returned 35 default-template results,
  all with native score attributes, correct local script/query input, no grouped
  layout. Counts/booleans only captured. This proves markup integration, not
  search relevance improvement or a visual Brave screenshot check.
- Full isolated validation reran successfully during the cooldown. Subsequent
  healthcheck correction passed resolved-code/policy checks; 99 host tests and
  DOM suite reran, and actual deployed health/gateway/VPN checks passed.
  Git closeout commits/pushes/merges the completed preview branch; old unrelated
  unmerged shadow-test branch is preserved. No installer or remote image release.

# Browser preferred-source preview

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
rollback image, waits for quiet, compares the built/validated manifests, replaces
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
- Deployment and final end-to-end localhost checks pending.

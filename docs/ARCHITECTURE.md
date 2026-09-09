# Architecture

## Product Path

Brave address bar -> `127.0.0.1:8085/search?q=...` -> localhost nginx gateway ->
SearXNG `search-provider` -> shared `search-vpn` namespace -> Proton WireGuard ->
configured search engines. Results render in SearXNG's native UI.

The gateway's VPN configuration targets only `search-vpn:8080`; Docker DNS
refreshes that fixed name every five seconds. It never chooses an upstream from
the incoming Host/query. Proxy failures return a local 503, not an external
provider redirect. This does not replace namespace-client recreation after
replacing the VPN container; use `start-proton-search.ps1 -Recreate`.

SearXNG uses the VPN-local DNS resolver. No LLM, backend ranking, page fetcher,
host redirector or automatic query expansion is on this browser path.

## Network Boundaries

- `host-gateway`: `host_access` and `core_internal`; only service publishing
  host ports, all bound to 127.0.0.1. Search is port 8085.
- `search-vpn`: `core_internal` and `egress`; kill-switched WireGuard and local
  encrypted-DNS forwarding. Restricted key file, never environment metadata.
- `search-provider`: shares VPN namespace and mounts its own read-only resolver.
- Host/browser traffic, including clicked result websites, remains unchanged.

The base Compose file still supports direct search egress for isolated validation
and historical development. It is NOT the privacy deployment for this PC. The
local `.env` selects the Proton overlay; scripts preserve that selection.

## Configuration Ownership

- `configs/searxng/settings.yml`: browser engines, timeouts and native UI defaults.
- SearXNG preferences/query syntax: explicit language, categories and engines;
  saved preferences may override defaults except locked privacy settings.
- `configs/localhost-gateway/nginx.proton-search.conf`: actual PC browser gateway.
- `scripts/test-browser-search.ps1`: manual fixed-fixture browser-route metrics.
- `SEARCH_*` and `GROUNDING_*` environment settings: legacy backend only; they
  do not tune the native SearXNG result list.

## Legacy Services Still Present

`ui`, `backend`, and `fetcher` remain in the current Compose/startup dependency
graph, with old UI/backend ports also published. The model is profile-gated and
internal-only. Browser search does not use those services, but nginx startup and
health still reference the old routes. Safely making deployment search-only
requires updating this graph, health checks, startup and validation together.
This is the next milestone, not an already completed migration.

Historical interfaces and network details are in LEGACY_ARCHITECTURE.md.

# Architecture

## Production Search Path

Brave -> 127.0.0.1:8085/search?q=... -> host-gateway -> SearXNG
(search-provider in search-vpn's namespace) -> Proton WireGuard -> engines.

SearXNG's native UI is the only interface. No chatbot, orchestrator, page fetcher,
local model or redirector participates in search or exists as a Compose service.

## Boundaries

- host-gateway: unprivileged nginx, core_internal + host_access; publishes only
  localhost search port 8085. Dynamic Docker DNS resolves a fixed search-vpn
  upstream, never a user-supplied hostname. No external outage redirect.
- search-provider: read-only SearXNG with its own VPN-local resolver mount;
  shares search-vpn's network namespace and publishes no host ports.
- search-vpn: core_internal + egress; Proton WireGuard, encrypted DNS, firewall.
  Only NET_ADMIN is added. Credential file is read-only, not environment metadata.
- Browser/host traffic and clicked result websites keep their normal networking.

Without the overlay, base Compose attaches search only to core_internal, so it
is offline rather than a direct-egress fallback. Isolated validation uses this
base plus docker-compose.validation.yml, a tmpfs cache and separate port/project.
Normal startup explicitly selects the Proton overlay. A replaced VPN namespace
still requires start-proton-search.ps1 -Recreate.

The manual News candidate is a disposable experiment process, not a service or
production import. Offline checks use network=none; an explicitly invoked trial
shares the existing VPN namespace with a separate tmpfs cache and no listener.
See ISOLATED_NEWS_CANDIDATE.md for cooldown limitations and deployment gates.

## Configuration

- configs/searxng/settings.yml: engines, timeouts and native privacy defaults.
- General ranking retains Brave/Yahoo/Bing, with Bing weight 0.35 after the
  informational audit. No query rewriting or model is on this path.
- Native preferences/query syntax: language, engines, categories and appearance.
- configs/localhost-gateway/nginx.proton-search.conf: production reverse proxy.
- .env: project/port/image/VPN configuration and SearXNG secret only. Old unused
  model/backend keys in pre-existing .env files have no consumers.
- Windows startup task calls a hidden helper that starts the three services.
  No Node daemon or fallback listener is needed.

## Future Local Refinement

A future reranker may run as a headless internal-only service, consuming already
returned results. It does not require the removed UI/backend/fetcher. Define its
contract, privacy boundaries and benchmark before implementation; none is added
or provisioned now. Historical architecture/code remains in Git and LEGACY docs.

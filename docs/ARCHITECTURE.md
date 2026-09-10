# Architecture

## Production Search Path

Brave -> 127.0.0.1:8085/search?q=... -> host-gateway -> SearXNG
(search-provider in search-vpn's namespace) -> Proton WireGuard -> engines.

SearXNG's native UI is the only interface. No chatbot, orchestrator, page fetcher,
local model or redirector participates in ordinary search. An explicitly opt-in
preview can reorder an already rendered result page; it is not the search path.

## Optional Browser Preference Preview

Native results page -> opt-in same-origin POST through gateway -> tmpfs Unix
socket -> separate network=none CPU reranker -> numeric permutation. Original
DOM nodes/order are retained in-page for instant OFF/ON comparison, no new search.
No new listener port or model network, no external inference, no query cache.
Only flat default-template lists/first 24 rows are eligible. Read
BROWSER_PREFERENCE_PREVIEW.md for limits, startup and rollback.

## Boundaries

- host-gateway: unprivileged nginx, core_internal + host_access; publishes only
  localhost search port 8085. Dynamic Docker DNS resolves a fixed search-vpn
  upstream, never a user-supplied hostname. No external outage redirect.
- search-provider: read-only SearXNG with its own VPN-local resolver mount;
  shares search-vpn's network namespace and publishes no host ports.
  Built locally from the pinned upstream image with a guarded publication-date
  merge and date-macro repair (images/searxng). No runtime patch loader.
- search-vpn: core_internal + egress; Proton WireGuard, encrypted DNS, firewall.
  Only NET_ADMIN is added. Credential file is read-only, not environment metadata.
- Browser/host traffic and clicked result websites keep their normal networking.

Without the overlay, base Compose attaches search only to core_internal, so it
is offline rather than a direct-egress fallback. Isolated validation uses this
base plus docker-compose.validation.yml, a tmpfs cache and separate port/project.
Validation builds use their own image tag, never replacing the production tag.
Normal startup explicitly selects the Proton overlay. A replaced VPN namespace
still requires start-proton-search.ps1 -Recreate.

The manual News candidate is a disposable experiment process, not a service or
production import. Offline checks use network=none; an explicitly invoked trial
shares the existing VPN namespace with a separate tmpfs cache and no listener.
Its live mode is retired after the failed trial; offline original-image tests
remain historical characterization. See ISOLATED_NEWS_CANDIDATE.md.

The separate guarded DDG web integration experiment is also not a service or
production import. Its network=none tests use a non-root container-loopback TLS
fixture with ephemeral trust/DNS overrides; no host ports, VPN or live cache.
It exercises native processor cooldowns and the real client while enforcing a
candidate-only deadline/body/header boundary. See DDG_WEB_NATIVE_INTEGRATION.md;
no live mode or production adapter installation is added.

The later separate test-ddg-web-trial.ps1 defaults to network=none initialization;
its explicit approved live run used only the existing VPN namespace after quiet/
cooldown and isolation checks. It has no listener, key/cache mount or production
installation. After a blocked first preflight, a user-confirmed quiet-window
trial returned one healthy query then timed out on the next initial fetch. Both
live entrypoints are now retired. See DDG_WEB_GUARDED_TRIAL.md; never weaken the
offline integration test boundary or treat the experiment as a deployment.

## Configuration

- configs/searxng/settings.yml: engines, timeouts and native privacy defaults.
- General ranking retains Brave/Yahoo/Bing, with Bing weight 0.35 after the
  informational audit. No query rewriting or model is on this path.
- Native preferences/query syntax: language, engines, categories and appearance.
- configs/localhost-gateway/nginx.proton-search.conf: production reverse proxy.
- .env: project/port/image/VPN configuration and SearXNG secret only. Old unused
  model/backend keys in pre-existing .env files have no consumers.
  SEARXNG_IMAGE is also inert: search uses the reviewed local build, not an
  environment override. Gateway/VPN image overrides still require digest pins.
- Windows startup task calls a hidden helper that starts the three services.
  No Node daemon or fallback listener is needed.

## Future Local Refinement

A future reranker may run as a headless internal-only service, consuming already
returned results. It does not require the removed UI/backend/fetcher. Define its
contract, privacy boundaries and benchmark before integration. A separately
approved CPU-only experiment is now provisioned: LOCAL_RERANKER_TRIAL.md.
Its disposable network-none runner has no listener or production connection;
the browser path above is unchanged. Historical architecture/code remains in Git
and LEGACY docs; no legacy runtime is restored.

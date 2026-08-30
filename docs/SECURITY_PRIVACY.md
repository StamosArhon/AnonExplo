# Security And Privacy

## Threat Model

This project assumes a local single-user workstation deployment. The main risks are:

- accidental exposure beyond localhost
- the model runtime gaining unnecessary network reach
- prompt or article text ending up in logs or tracked files
- the fetcher being abused to read local or private network targets
- service sprawl causing unclear trust boundaries

## Security Defaults

- The host-facing UI, backend, and optional standalone SearXNG entrypoints bind to `127.0.0.1` only through a dedicated localhost gateway service.
- The model backend stays on an internal-only Docker network.
- Search and fetch services are the only default services that join the egress-capable network.
- The bundled SearXNG web UI is reachable only through the localhost gateway; the search container itself is still not published directly to the host.
- The default SearXNG profile uses a bounded curated multi-engine set (`brave`, `bing`, plus specialized sources) and bounded upstream timeouts; each enabled engine is a separate outbound recipient, and clearing or widening `SEARCH_ENGINES` deliberately increases both query exposure and availability variability.
- Optional browser address-bar integration should point browser profiles at a localhost-only redirector, not directly at SearXNG, when DuckDuckGo fallback is desired for local SearXNG outages.
- Repo-managed services run as non-root where practical.
- Capabilities are dropped and `no-new-privileges` is enabled where practical.
- Compose validation now checks expected network membership, localhost-only publication, digest-pinned third-party images, and local-only CORS origins before a branch is declared ready.
- No remote frontend assets, fonts, telemetry, analytics, or CDNs are used.
- Grounded model prompts use bounded source-context limits so fetched page text is not forwarded to the model without size controls.
- If article fetches fail but search still returns usable snippets, the backend may now use bounded search-result snippets as an explicit fallback grounding mode instead of silently falling back to model prior knowledge.
- Preferred-domain ranking bias may influence which already-returned search results are fetched first, but it must not silently become a hidden second search provider or a provider-specific bypass path.
- The current fetcher-resilience pass keeps direct HTML fetches only and does not add third-party reader proxies or hidden publisher-specific bypasses, because those would change the privacy and trust model.
- The Wikimedia-specific route, when enabled, must stay explicit, documented, and based on an official interface rather than a stealthy robot-policy bypass.
- The optional `docker-compose.proton-search.yml` overlay routes only the SearXNG/search-provider network namespace through a Proton WireGuard gateway. It does not become a host-wide VPN route, and it publishes no VPN or search-container port.
- The VPN gateway is an intentional security exception: it requires `NET_ADMIN` and `/dev/net/tun` to establish the tunnel, while retaining `no-new-privileges` and a read-only root filesystem where compatible. The gateway firewall must stay enabled as the kill switch.
- A separate Proton WireGuard configuration/private key must be generated for this PC. Do not reuse the homeserver's tunnel identity or commit the key. The same Proton account may be used if its simultaneous-connection allowance permits it.
- A VPN changes the source IP seen by upstream search engines and hides the query from the ISP's traffic path, but it does not stop an upstream search engine from seeing or retaining the plaintext query. This overlay therefore improves egress separation and may improve or worsen upstream availability; it is not a zero-visibility search index.

## Secrets Handling

- Keep secrets in local untracked files such as `.env`.
- Never commit tokens, cookies, API keys, or private model access credentials.
- Model files and fetched content are local assets, not Git assets.
- The bootstrap flow generates a local `SEARXNG_SECRET` in `.env` for the default search-provider path.
- The optional Proton search profile reads `PROTON_WIREGUARD_PRIVATE_KEY` from the untracked `.env`; it must never be copied into the repository, logs, Compose output, or documentation.
- The default model provisioning flow downloads the GGUF on the host into `data/models/` and verifies it against a tracked SHA256 value; the model container itself does not fetch weights at runtime.

## Logging Guidance

- Keep logs operational, not archival.
- Do not add debug logging that dumps prompts, full fetched article bodies, headers, or provider payloads by default.
- If deeper logging is ever added for troubleshooting, it must be temporary and documented.
- VPN troubleshooting must not print the WireGuard private key, full `.env`, or provider configuration into command output or repository files.
- Repo-managed UI, backend, fetcher, and localhost-gateway services suppress routine access logging where practical so request paths do not become default operational noise.
- The local UI may remember the selected model id, saved local instruction text, and direct-chat history in browser local storage on the same workstation.
- Grounded-answer transcripts, fetched source details, and fetch-inspector output must remain non-persistent by default.
- Because direct-chat history is now browser-local persistent state, the UI must keep explicit delete and purge controls, label that storage clearly as browser-local and device-local, and must not silently expand that storage to grounded searches or fetched page bodies.
- If `MODEL_PROVIDER=ollama` is used, keep `MODEL_BASE_URL` on a local or otherwise trusted private endpoint; do not silently treat a hosted Ollama API as equivalent to a local runtime from a privacy perspective.
- If the optional browser search redirector is configured with DuckDuckGo fallback, address-bar queries are sent to DuckDuckGo only when the local SearXNG route is unavailable. Disable or replace that fallback on devices that must never send browser search queries to an external provider.

## Fetcher Controls

The fetcher is the most sensitive service because it has egress. Current guardrails:

- only `http` and `https` URLs are accepted
- obvious localhost and private-address targets are rejected
- response size is capped
- the backend-to-fetcher timeout is kept separate from the fetcher-to-publisher timeout so structured fetcher failures can propagate instead of being hidden behind a generic orchestration timeout
- non-HTML responses are rejected
- extracted text is trimmed to a bounded size
- oversized live pages may still produce bounded partial extracts with explicit warnings when the early portion of the document is already usable grounded material
- thin page extractions are classified explicitly instead of being treated as trustworthy article text
- blocked or rate-limited upstream responses are surfaced with structured failure codes so operators can tell why grounding degraded
- grounded-answer prompts use only bounded excerpts of fetched source text
- bounded search-result snippets may be used as a clearly labeled fallback when article fetches fail
- the deliberate baseline is direct HTML fetch plus explicit snippet fallback, with an optional official Wikimedia API path for supported Wikimedia article URLs
- Wikimedia API use should include a descriptive, contactable user-agent string configured by the operator before the opt-in path is enabled
- no stealth Wikipedia or publisher-specific robot-policy bypasses should be introduced without an explicit privacy review and a documented official access path

These controls reduce privacy leakage and resource abuse, but they are not a substitute for host firewall policy.

If `SEARCH_PROVIDER=yacy` is used, review YaCy's own peer-to-peer or network settings deliberately. It is supported as a replaceable search adapter, but its privacy posture depends on how the YaCy instance itself is configured.

## Defense In Depth

Docker internal networks reduce accidental reachability, but they are not a complete security boundary if a container is compromised. Recommended follow-up hardening:

- keep the localhost gateway as small and low-privilege as practical, because it is the one default service that must sit on a non-internal bridge for host browser access, including the optional SearXNG browser route
- host firewall rules that restrict outbound traffic for non-egress services
- explicit model file provisioning and checksum verification
- tighter container filesystem constraints where compatible with the chosen runtime
- periodic dependency and image review

See `docs/OPERATIONS_AND_MAINTENANCE.md` for the current Windows-host firewall guidance and operational recovery notes.

## Out Of Scope For Now

- public internet exposure
- multi-user auth and RBAC
- external identity providers
- long-term grounded source storage

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
- Repo-managed services run as non-root where practical.
- Capabilities are dropped and `no-new-privileges` is enabled where practical.
- Compose validation now checks expected network membership, localhost-only publication, digest-pinned third-party images, and local-only CORS origins before a branch is declared ready.
- No remote frontend assets, fonts, telemetry, analytics, or CDNs are used.
- Grounded model prompts use bounded source-context limits so fetched page text is not forwarded to the model without size controls.

## Secrets Handling

- Keep secrets in local untracked files such as `.env`.
- Never commit tokens, cookies, API keys, or private model access credentials.
- Model files and fetched content are local assets, not Git assets.
- The bootstrap flow generates a local `SEARXNG_SECRET` in `.env` for the default search-provider path.
- The default model provisioning flow downloads the GGUF on the host into `data/models/` and verifies it against a tracked SHA256 value; the model container itself does not fetch weights at runtime.

## Logging Guidance

- Keep logs operational, not archival.
- Do not add debug logging that dumps prompts, full fetched article bodies, headers, or provider payloads by default.
- If deeper logging is ever added for troubleshooting, it must be temporary and documented.
- Repo-managed UI, backend, fetcher, and localhost-gateway services suppress routine access logging where practical so request paths do not become default operational noise.
- The local UI may remember the selected model id, saved local instruction text, and direct-chat history in browser local storage on the same workstation.
- Grounded-answer transcripts, fetched source details, and fetch-inspector output must remain non-persistent by default.
- Because direct-chat history is now browser-local persistent state, the UI must keep explicit delete and purge controls and must not silently expand that storage to grounded searches or fetched page bodies.
- If `MODEL_PROVIDER=ollama` is used, keep `MODEL_BASE_URL` on a local or otherwise trusted private endpoint; do not silently treat a hosted Ollama API as equivalent to a local runtime from a privacy perspective.

## Fetcher Controls

The fetcher is the most sensitive service because it has egress. Current guardrails:

- only `http` and `https` URLs are accepted
- obvious localhost and private-address targets are rejected
- response size is capped
- non-HTML responses are rejected
- extracted text is trimmed to a bounded size
- grounded-answer prompts use only bounded excerpts of fetched source text

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

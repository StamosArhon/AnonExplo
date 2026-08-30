# Instructions And Notes

## Coding Standards

- Keep services small and explicit.
- Prefer standard library features unless a dependency clearly earns its place.
- Keep provider integration behind narrow interfaces so future adapters can be added without reshaping the whole app.
- Favor predictable error messages over clever abstractions.

## Documentation Standards

- Update `docs/IMPLEMENTATION_ROADMAP.md` whenever architecture, phase status, validation status, or next steps change.
- Update `README.md` when setup steps or repo structure change.
- Update `docs/ARCHITECTURE.md` and `docs/SECURITY_PRIVACY.md` when the effective design or threat assumptions change.
- Update `docs/OPERATIONS_AND_MAINTENANCE.md` when startup, maintenance, recovery, or firewall guidance changes.

## Security Rules

- Localhost-only exposure is the baseline.
- The model runtime must remain off egress-capable networks unless explicitly documented otherwise.
- Do not add telemetry, analytics, or remote web assets.
- Do not persist prompts, fetched article bodies, or search history unless a later milestone explicitly defines a privacy-reviewed storage policy.
- Reject obvious localhost and private-address fetch targets in the fetcher to reduce SSRF-style misuse inside the local stack.

## Local-Only Assumptions

- This project is optimized for a single-user local workstation flow first.
- Public reverse proxying, multi-user auth, and remote access are out of scope unless a later milestone introduces them deliberately.
- The default hardware target is roughly an i7 CPU, 16 GB RAM, and an RTX 2070 Super.

## Configuration Conventions

- `.env.example` is the tracked configuration template.
- `.env` is untracked and machine-specific.
- Provider selection must be controlled through environment variables first, not code edits.
- Model files are local assets and must not be committed.
- The first concrete local model runtime profile is documented in `docs/LLAMA_CPP_RUNTIME_PROFILE.md`.
- If `.env` predates the latest repo template, treat `.env.example` as the source of truth for new model-runtime keys and update the local file deliberately instead of relying on stale placeholders.

## Branch / Merge Workflow

- Always use `stamos/<branch-name>`.
- Keep branches narrow.
- After merge, delete the completed working branch locally and remotely.
- If a branch changes recurring repo rules, update `AGENTS.md` in the same branch.

## Practical Notes

- The first branch intentionally keeps the UI static and lightweight to avoid introducing a frontend toolchain before the architecture is stable.
- The current model slot is a concrete `llama.cpp` CUDA profile, but the backend remains adapter-driven and should not be coupled to that runtime.
- The default validated model path is `QuantFactory/Qwen2.5-7B-Instruct-GGUF` with the file `Qwen2.5-7B-Instruct.Q4_K_M.gguf` stored in `data/models/`.
- The tracked checksum for that default file is `4e9221217000d0fc8f5ffdbae51a7201fcc3613de18ff1b1cd8c7c01f924437b`.
- Use `scripts/provision-default-model.ps1` to populate `data/models/` and `scripts/validate.ps1 -RequireModelRuntime` to confirm the full path.
- Use `scripts/ops-check.ps1` for lightweight checks on an already-running stack.
- The current UI now stores browser-local direct chat history, the selected model id, and saved direct-chat or grounded-answer instructions in local storage on the same workstation.
- Keep the UI explicit that direct-chat history is browser-local and device-local, not synced or server-side state.
- Keep direct-chat history actions grouped with the history list in the sidebar so `New`, `Purge`, and per-entry delete controls read as one local-history surface instead of scattered controls.
- Grounded-answer transcripts, fetched source details, and fetch-inspector output must stay transient unless a later milestone adds a privacy-reviewed storage design first.
- Keep `Direct Chat` and `Grounded Answer` semantically explicit in both code and copy. Direct Chat is model only; Grounded Answer is the search plus fetch plus model workflow.
- Keep grounded-answer provenance discreet in the main thread. Superscript-style citation references, hover tooltips, and an on-demand source drawer are preferred over large in-line controls or a permanently expanded diagnostics block.
- Keep source-preview hover cards in a floating overlay outside the scroll shell or other clipped containers. Do not render tooltip content directly inside the message markup if that would make it vulnerable to `overflow` clipping or whitespace-driven layout drift.
- Avoid duplicating grounded-answer source controls across multiple surfaces. One quiet per-answer source action plus the source drawer is preferred over repeating large source buttons in both the thread and the workspace header.
- Grounded Answer now prefers fetched article text but may fall back to bounded search snippets when fetches fail. Treat `grounding.summary.context_mode` as the source of truth for which path was used.
- Mixed grounding is now valid too: `fetched_plus_snippets` means fetched article text was available for part of the source set and bounded snippet fallback was appended for selected sources whose fetches failed. Keep fetched text preferred in prompts, copy, and future logic.
- Keep query-term normalization symmetric between the query and the source text. If you tune grounded ranking or excerpt selection later, do not regress back to matching canonical variants on only one side.
- Do not let single-passage excerpt shortcuts fire for clearly multi-part grounded questions. Smaller local models answer better when each major clause of the question is represented in the supplied evidence.
- Keep grounded-answer citation syntax canonical as consecutive source IDs like `[S1][S2]`. Normalize that shape in the backend, and keep the UI tolerant of grouped or repeated citation formats as a rendering fallback rather than trusting raw model output.
- Do not go back to naive head-only article truncation for grounded answers. Query-relevant excerpt selection from fetched pages is now part of answer quality, especially for smaller local models.
- The grounding summary's `selected_sources` count is now effectively "selected or attempted" because the backend can try later ranked sources after early fetch failures.
- The fetcher now exposes structured error details such as `blocked_by_remote_policy`, `upstream_forbidden`, `upstream_rate_limited`, and `content_too_thin`; keep those codes explicit in backend and UI surfaces instead of collapsing them into generic fetch failures.
- Use the tracked fetcher knobs in `.env.example` when tuning extraction quality: `FETCH_MIN_CONTENT_CHARS`, `FETCH_MIN_WORD_COUNT`, and `FETCH_ACCEPT_LANGUAGE`.
- The default SearXNG search profile uses `SEARCH_CATEGORIES=auto`: ordinary questions use `general`, while current/news-like questions use `general,news`. Keep `SEARCH_CATEGORIES=general,news` when an operator explicitly wants both categories for every query.
- The default SearXNG engine list is intentionally curated through `SEARCH_ENGINES` to balance general-search redundancy against the privacy and latency cost of sending a query to more upstreams. The validated general set includes `brave` and `bing`; Qwant, Mojeek, Google, and Yahoo were tested on the current network but did not provide usable general results, so they stay out of the default profile. With `SEARCH_CATEGORIES=auto`, news-engine names are kept out of ordinary queries and added for current/news-like queries. Clear it only when the operator accepts wider engine coverage and more upstream variability.
- The SearXNG `outgoing.request_timeout` is deliberately moderate. Increasing it can improve coverage from slow upstreams but also increases search latency; keep the backend request timeout above the SearXNG budget.
- Grounded search may issue up to `GROUNDING_MAX_QUERY_VARIANTS` bounded queries for clearly multi-part questions. The original query remains one variant, and the backend records partial variant failures instead of discarding successful results.
- Keep `FETCHER_CLIENT_TIMEOUT_SECONDS` slightly higher than `FETCH_REQUEST_TIMEOUT_SECONDS`. The backend-to-fetcher wait budget must outlast the fetcher-to-publisher wait budget so structured fetcher error details are not lost behind a blank orchestrator timeout.
- Do not revert the fetcher to hard-fail immediately on oversized live pages when bounded partial HTML already contains usable text. The current baseline prefers explicit `direct_html_partial` warnings over unnecessary total failure.
- Use `SEARCH_PREFERRED_DOMAINS` and `SEARCH_PREFERRED_DOMAIN_BOOST` when you want grounded-source ranking to modestly favor trusted domains such as Wikipedia or Wikimedia. Keep that preference modest; it should bias ranking, not replace search relevance or domain diversity.
- If Wikimedia API support is enabled, require a descriptive and contactable `FETCH_WIKIMEDIA_API_USER_AGENT` in `.env` instead of relying on the generic fetch user-agent.
- Request-level model selection should stay bounded to runtime-advertised models and should not mutate the backend's configured default model.
- Do not reintroduce a backend orchestration dependency on one hard-coded search service name; provider switching should remain env-driven at the backend boundary.
- Keep the host-facing UI and backend access path behind the dedicated localhost gateway unless there is a documented reason to publish app containers directly.
- If the bundled SearXNG web UI is exposed for standalone use, route it through the same localhost gateway rather than publishing the search container directly.
- If a machine configures Brave, Helium, or another Chromium-family browser to use bundled SearXNG from the address bar, prefer `scripts/setup-browser-search.ps1` and follow `docs/BROWSER_SEARCH_INTEGRATION.md`: browsers should point at the local fallback redirector on `127.0.0.1:8095`, not directly at `127.0.0.1:8085`, and Brave should be verified to show `AnonExplo SearXNG (Default)` because adding the engine alone may not make it the active default.
- Browser-search startup must stay non-disruptive: use hidden VBS launchers for the redirector and stack starter, and use `docker desktop start --detach` rather than foreground-launching `Docker Desktop.exe`.
- Future branches should prefer expanding functionality through adapters and configuration rather than adding direct service-to-service coupling.
- `scripts/validate.ps1` now enforces the intended Compose hardening model, including localhost-only publication, expected network membership, digest-pinned third-party images, and local-only CORS origins.
- Some publishers and Wikipedia paths can still block fetches from the container runtime. The current fallback is explicit snippet-grounding, not silent prior-knowledge answering.
- Do not add stealthy Wikipedia or publisher-specific robot-policy bypasses. Wikimedia support, when enabled, must use an explicit official API path, document the privacy and maintenance tradeoff, and remain opt-in.
- The current fetcher-resilience pass does not add third-party reader proxies or special Wikipedia bypasses. If a future branch adds a secondary reader strategy, document the privacy tradeoff and make it opt-in.
- The current baseline decision is to keep direct HTML fetch plus explicit snippet fallback as the steady-state design rather than adding a secondary reader path.
- The optional Proton search profile lives in `docker-compose.proton-search.yml` and uses a container-scoped WireGuard sidecar. Start it with `scripts/start-proton-search.ps1`; never turn on a host-wide VPN just to protect AnonExplo search traffic.
- Generate a separate Proton WireGuard configuration/private key for this PC even when the same Proton account is already used by the homeserver. Keep the key only in the untracked `.env`; the overlay's Gluetun firewall must remain the no-direct-egress kill switch.
- The search-only VPN changes the egress IP and ISP visibility but does not prevent upstream search engines from receiving plaintext queries. Do not describe it as eliminating provider-side query visibility or retention.

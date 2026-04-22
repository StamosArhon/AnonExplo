# AnonExplo

AnonExplo is a privacy-first, self-hosted local-LLM stack for local use on personal machines. The project is designed so the local model runtime and the anonymized search provider can be swapped through configuration without rewriting the whole system.

## Current Status

This repository is currently focused on turning the secure local stack into a practical daily-use workbench. The repo now provides:

- the durable repo protocol for future Codex threads
- the initial architecture and security documents
- a Docker Compose foundation with local-only exposure and network isolation
- a working grounded search-to-fetch backend flow with structured source/error output
- a grounded-answer path that passes fetched source text into the configured local model
- provider abstraction points for the model and search layers
- a concrete `llama.cpp` CUDA runtime profile for the first local model path
- a repo-managed provisioning script for the default GGUF baseline
- runtime readiness reporting in the backend and UI
- end-to-end validation of the default local model path on the current development machine
- a static local workbench with browser-local model selection and clearer runtime or failure inspection
- backend adapters for both OpenAI-compatible runtimes and native Ollama APIs
- backend adapters for both SearXNG and YaCy search services
- a localhost gateway service that makes the UI and backend reachable on Docker Desktop while keeping the app services on internal networks
- an optional localhost-only SearXNG web UI route for standalone searching when you do not want the LLM workflow
- a calmer sidebar-and-editorial UI shell with settings and stack details moved into modals instead of the main chat area
- browser-local direct chat history with per-entry delete and full purge controls
- compact direct-chat history cards with integrated delete actions instead of a split or awkward sidebar row layout
- direct-chat history actions now live inside the same sidebar history panel so `New`, `Purge`, and the local chat list read as one coherent browser-local area
- stronger browser-local history labeling so it is clear that direct chat history is device-local, purgeable, and not synced or stored server-side
- explicit workspace separation so `Direct Chat` stays model only while `Grounded Answer` is the path that uses SearXNG plus fetched source text
- superscript-style grounded source references with hover tooltips plus a retractable source drawer so provenance stays available without overwhelming the main answer surface
- config-driven SearXNG tuning defaults for broader current-events coverage, including categories, language, and optional engine or time-range controls
- config-driven preferred-domain ranking bias for grounded search, with Wikipedia and Wikimedia as the default example so encyclopedic sources surface more reliably when relevant
- ranked grounded-source selection with retry behavior so later sources can still be fetched when early candidates fail
- structured fetcher failure codes, thin-content detection, and domain-aware retry behavior so blocked publishers are easier to understand without silently degrading into generic errors
- an explicit snippet-fallback grounding mode for cases where search works but article fetches are blocked, with the UI showing whether an answer came from fetched text or search snippets
- an opt-in official Wikimedia API fetch path for supported Wikimedia article URLs when direct HTML fetching is not the right fit
- quieter default logging across the repo-managed UI, backend, fetcher, and localhost gateway services
- an operations guide plus a lightweight stack health-check script for daily local maintenance

## Design Goals

- Local use only by default
- Custom local UI, not a hosted SaaS UI
- Clear boundaries between:
  - UI
  - backend or orchestrator
  - model runtime
  - anonymized search provider
  - page fetch and read pipeline
- Config-driven provider selection
- Least-privilege defaults
- Minimal manual work when reproducing the setup on another machine

## Initial Architecture

- `apps/ui`
  - local static UI that talks only to the orchestrator
- `apps/backend`
  - FastAPI orchestrator with model, grounded search/fetch, and provider abstraction points
- `services/fetcher`
  - FastAPI service that fetches, parses, and normalizes article text
- `search-provider`
  - default example is SearXNG behind an internal service name, with an optional localhost-only browser route through the host gateway
- `model-backend`
  - profile-gated `llama.cpp` CUDA runtime slot with pinned image and GGUF-driven config

See `docs/ARCHITECTURE.md` for the fuller design.

## Quick Start

1. Bootstrap local files:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
   ```

2. Review `.env` and adjust provider settings as needed.
   The bootstrap script generates a local `SEARXNG_SECRET` value automatically for new environments.
   If `.env` predates the current repo template and still contains placeholder model settings, copy the current model-runtime keys from `.env.example`.

3. Provision the default local GGUF model:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/provision-default-model.ps1
   ```

4. Run the full validation path, including the model runtime probe:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime
   ```

5. Start the pinned llama.cpp runtime profile:

   ```powershell
   docker compose --profile llamacpp up -d model-backend
   ```

6. Start the base stack:

   ```powershell
   docker compose up --build host-gateway ui backend fetcher search-provider
   ```

7. Open the local UI at `http://127.0.0.1:3000`.

   The localhost entrypoint is the dedicated `host-gateway` proxy. It exposes the UI on port `3000`, the backend API on port `8000`, and the bundled SearXNG web UI on port `8085` while the `ui`, `backend`, and `search-provider` containers themselves remain on internal Docker networks.

8. Optional: open the standalone SearXNG UI at `http://127.0.0.1:8085`.

9. Use the local UI's workspaces to switch between direct chat, grounded answers, and fetch inspection.
   `Direct Chat` is model only. `Grounded Answer` is the mode that uses SearXNG, page fetches, and source-backed synthesis.
   The workbench stores the selected model, saved local instructions, and direct-chat history in browser local storage on the same device only. Direct-chat history is purgeable from the sidebar, is not synced, and is not stored as server-side chat history. Grounded-answer details and fetch results stay transient in the current tab by default.

10. Run the lightweight operator check when the stack is up:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1 -RequireModelRuntime
   ```

## Provider Switching

The repo treats provider choice as configuration:

- model runtime:
  - `MODEL_PROVIDER`
  - `MODEL_BASE_URL`
  - `MODEL_NAME`
- search provider:
  - `SEARCH_PROVIDER`
  - `SEARCH_BASE_URL`
  - `SEARCH_CATEGORIES`
  - `SEARCH_LANGUAGE`
  - `SEARCH_TIME_RANGE`
  - `SEARCH_ENGINES`
  - `SEARCH_PREFERRED_DOMAINS`
  - `SEARCH_PREFERRED_DOMAIN_BOOST`
- fetch service:
  - `FETCH_BASE_URL`
  - `FETCH_MIN_CONTENT_CHARS`
  - `FETCH_MIN_WORD_COUNT`
  - `FETCH_ACCEPT_LANGUAGE`
  - `FETCH_WIKIMEDIA_API_ENABLED`
  - `FETCH_WIKIMEDIA_API_USER_AGENT`

The current implementation supports these provider adapters:

- model runtime:
  - `openai_compatible`
  - `ollama`
- search provider:
  - `searxng`
  - `yacy`

Recommended local examples:

- `MODEL_PROVIDER=openai_compatible` with `MODEL_BASE_URL=http://model-backend:8080/v1`
- `MODEL_PROVIDER=ollama` with `MODEL_BASE_URL=http://host.docker.internal:11434/api` or another local/private Ollama endpoint
- `SEARCH_PROVIDER=searxng` with `SEARCH_BASE_URL=http://search-provider:8080`
- `SEARCH_PROVIDER=yacy` with `SEARCH_BASE_URL=http://yacy-search:8090`

For privacy-first deployments, keep Ollama pointed at a local or otherwise trusted private endpoint rather than a hosted cloud API, and review YaCy's own network/peer settings before treating it as equivalent to SearXNG from a privacy standpoint.

## Grounding Flow

The repo now supports a practical grounded-answer path:

1. search through the configured search provider
2. rank and dedupe candidate sources with domain diversity, query-relevance heuristics, and an optional preferred-domain bias for trusted encyclopedic domains such as Wikipedia or Wikimedia
3. fetch and parse readable page text through the fetcher, classifying blocked or thin pages and retrying later candidates when earlier fetches fail
4. construct a bounded grounding context from fetched sources, or fall back to bounded search snippets when article fetches are unavailable
5. pass that context into the configured model runtime with explicit citation-only instructions

The UI now surfaces grounded provenance through superscript-style source references, hover tooltips, and an on-demand source drawer rather than a permanently expanded diagnostics block. It still keeps the current grounding mode (`fetched_text` or `search_snippets`) explicit. The current baseline deliberately uses direct HTML fetches plus explicit snippet fallback; it does not bundle a secondary reader proxy or hidden publisher-specific bypass. If you want the model to answer from current sourced material rather than its own prior knowledge, use `Grounded Answer`, not `Direct Chat`.

If you want supported Wikimedia article URLs to use an official Wikimedia interface instead of the default direct HTML path, enable `FETCH_WIKIMEDIA_API_ENABLED=true` and set a descriptive, contactable `FETCH_WIKIMEDIA_API_USER_AGENT` in `.env`. When enabled, supported Wikimedia article pages are fetched through the official Parse API and still flow through the same bounded extraction pipeline.
The preferred-domain ranking bias does not force every query into Wikipedia or run a second hidden provider. It simply gives configured domains a modest lift when they already appear in the search results and still look relevant to the query.

## UI Workbench

The local UI is still static and self-hosted, but it now behaves like a real workbench instead of a demo page:

- it loads provider, runtime, and model-catalog state from the backend
- it uses a calmer sidebar-and-editorial shell with settings and stack details in dedicated modals
- it keeps a browser-local direct chat history with `New`, per-entry delete, and full purge controls in the same sidebar history panel
- it labels that history clearly as browser-local and device-local so it is not mistaken for synced or server-side storage
- it lets you choose the requested model globally for direct-chat and grounded-answer requests
- it stores the selected model plus saved direct-chat and grounded-answer instructions locally in the browser
- it keeps grounded-answer transcripts, fetched source details, and fetch-inspector output transient in the current tab by default
- it makes the mode boundary explicit: direct chat is model only, grounded answer is search plus fetch plus model
- it surfaces runtime readiness, configured default vs. request override, and clearer failure cards without leaving stack diagnostics in the middle of the main chat surface
- it embeds grounded citations as superscript-style source references with hover tooltips and keeps the fuller source list behind one quiet per-answer source action plus a dedicated right-side drawer
- it keeps grounded-answer context-mode visibility explicit so you can tell whether an answer used fetched article text or search-snippet fallback

## Llama.cpp Profile

The first concrete model runtime profile is documented in `docs/LLAMA_CPP_RUNTIME_PROFILE.md`. It uses the `llama.cpp` OpenAI-compatible server image pinned to a digest, aliases the configured model name explicitly, and is tuned for a practical 4B to 8B GGUF baseline on the target machine class.

The current default model artifact is:

- source: `QuantFactory/Qwen2.5-7B-Instruct-GGUF`
- file: `Qwen2.5-7B-Instruct.Q4_K_M.gguf`
- sha256: `4e9221217000d0fc8f5ffdbae51a7201fcc3613de18ff1b1cd8c7c01f924437b`

## Validation

Run the repo validation script before shipping changes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
```

For the full local-model path, require the runtime probe:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime
```

For daily operations, see `docs/OPERATIONS_AND_MAINTENANCE.md`.

## Repository Layout

```text
.
|-- AGENTS.md
|-- README.md
|-- docker-compose.yml
|-- docs/
|-- apps/
|   |-- backend/
|   `-- ui/
|-- services/
|   `-- fetcher/
|-- configs/
|   `-- searxng/
`-- scripts/
```

## Continuity

Fresh Codex threads should start with `AGENTS.md` and `docs/IMPLEMENTATION_ROADMAP.md` before making changes.

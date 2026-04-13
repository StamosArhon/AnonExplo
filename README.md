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
- explicit workspace separation so `Direct Chat` stays model only while `Grounded Answer` is the path that uses SearXNG plus fetched source text

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
   The workbench stores the selected model, saved local instructions, and direct-chat history in browser local storage. Grounded-answer details and fetch results stay transient in the current tab by default.

## Provider Switching

The repo treats provider choice as configuration:

- model runtime:
  - `MODEL_PROVIDER`
  - `MODEL_BASE_URL`
  - `MODEL_NAME`
- search provider:
  - `SEARCH_PROVIDER`
  - `SEARCH_BASE_URL`
- fetch service:
  - `FETCH_BASE_URL`

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
2. dedupe and select candidate sources
3. fetch and parse readable page text through the fetcher
4. construct a bounded grounding context from fetched sources
5. pass that context into the configured model runtime

The UI also surfaces per-source fetch failures and the exact source text slice used for grounding. If you want the model to answer from current sourced material rather than its own prior knowledge, use `Grounded Answer`, not `Direct Chat`.

## UI Workbench

The local UI is still static and self-hosted, but it now behaves like a real workbench instead of a demo page:

- it loads provider, runtime, and model-catalog state from the backend
- it uses a calmer sidebar-and-editorial shell with settings and stack details in dedicated modals
- it keeps a browser-local direct chat history with a new-chat action, per-entry delete, and full purge
- it lets you choose the requested model globally for direct-chat and grounded-answer requests
- it stores the selected model plus saved direct-chat and grounded-answer instructions locally in the browser
- it keeps grounded-answer transcripts, fetched source details, and fetch-inspector output transient in the current tab by default
- it makes the mode boundary explicit: direct chat is model only, grounded answer is search plus fetch plus model
- it surfaces runtime readiness, configured default vs. request override, and clearer failure cards without leaving stack diagnostics in the middle of the main chat surface

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

# AnonExplo

AnonExplo is a privacy-first, self-hosted local-LLM stack for local use on personal machines. The project is designed so the local model runtime and the anonymized search provider can be swapped through configuration without rewriting the whole system.

## Current Status

This repository is currently focused on the `grounding-vertical-slice` milestone. The repo now provides:

- the durable repo protocol for future Codex threads
- the initial architecture and security documents
- a Docker Compose foundation with local-only exposure and network isolation
- a working grounded search-to-fetch backend flow with structured source/error output
- a grounded-answer path that passes fetched source text into the configured local model
- provider abstraction points for the model and search layers
- a concrete `llama.cpp` CUDA runtime profile for the first local model path

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
  - default example is SearXNG behind an internal service name
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

3. Start the base stack:

   ```powershell
   docker compose up --build ui backend fetcher search-provider
   ```

4. Open the local UI at `http://127.0.0.1:3000`.

5. Provision a local GGUF model in `data/models/`, review `.env`, and enable the pinned llama.cpp profile:

   ```powershell
   docker compose --profile llamacpp up -d model-backend
   docker compose up --build ui backend fetcher search-provider
   ```

6. Use the local UI's grounded-answer panel to search, fetch, inspect sources, and synthesize an answer from retrieved page text.

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

The current implementation targets an OpenAI-compatible local model endpoint plus SearXNG, but the orchestrator is intentionally structured so more adapters can be added in future branches.

## Grounding Flow

The repo now supports a practical grounded-answer path:

1. search through the configured search provider
2. dedupe and select candidate sources
3. fetch and parse readable page text through the fetcher
4. construct a bounded grounding context from fetched sources
5. pass that context into the configured model runtime

The UI also surfaces per-source fetch failures and the exact source text slice used for grounding.

## Llama.cpp Profile

The first concrete model runtime profile is documented in `docs/LLAMA_CPP_RUNTIME_PROFILE.md`. It uses the `llama.cpp` OpenAI-compatible server image pinned to a digest and is tuned for a practical 4B to 8B GGUF baseline on the target machine class.

## Validation

Run the repo validation script before shipping changes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
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

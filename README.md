# AnonExplo

AnonExplo is a privacy-first, self-hosted local-LLM stack for local use on personal machines. The project is designed so the local model runtime and the anonymized search provider can be swapped through configuration without rewriting the whole system.

## Current Status

This repository is in the `foundation-bootstrap` milestone. The first branch establishes:

- the durable repo protocol for future Codex threads
- the initial architecture and security documents
- a Docker Compose foundation with local-only exposure and network isolation
- a small but real skeleton for the UI, orchestrator, and fetch/read service
- provider abstraction points for the model and search layers

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
  - FastAPI orchestrator with model, search, and fetch abstraction points
- `services/fetcher`
  - FastAPI service that fetches, parses, and normalizes article text
- `search-provider`
  - default example is SearXNG behind an internal service name
- `model-backend`
  - profile-gated example slot for an OpenAI-compatible local model runtime such as `llama.cpp`

See `docs/ARCHITECTURE.md` for the fuller design.

## Quick Start

1. Bootstrap local files:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
   ```

2. Review `.env` and adjust provider settings as needed.

3. Start the base stack:

   ```powershell
   docker compose up --build ui backend fetcher search-provider
   ```

4. Open the local UI at `http://127.0.0.1:3000`.

5. Optionally enable the example llama.cpp profile after setting `MODEL_RUNTIME_IMAGE`, `MODEL_RUNTIME_COMMAND`, and provisioning a local GGUF model:

   ```powershell
   docker compose --profile llamacpp up --build
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
- fetch service:
  - `FETCH_BASE_URL`

The initial code targets an OpenAI-compatible local model endpoint plus SearXNG, but the orchestrator is intentionally structured so more adapters can be added in future branches.

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

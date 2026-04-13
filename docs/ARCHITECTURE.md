# Architecture

## Overview

AnonExplo uses a local-first, privacy-first service layout:

- `host-gateway`
  - localhost-only reverse proxy that exposes the UI, backend, and optional standalone SearXNG UI to the host without putting those app services directly on a non-internal Docker network
- `ui`
  - local browser interface for prompts, model selection, provider status, and grounding inspection
- `backend`
  - orchestrator that owns provider routing and exposes a stable local API
- `model-backend`
  - isolated local inference runtime
- `search-provider`
  - anonymized search service, default example SearXNG
- `fetcher`
  - page fetch and read pipeline that turns URLs into readable text

## Service Boundaries

The UI must only talk to the backend. The backend may talk to the model backend, search provider, and fetcher. The model backend should never need direct internet access.

## Network Topology

```mermaid
flowchart LR
    User["Local Browser"] --> Gateway["Host Gateway (127.0.0.1)"]
    Gateway --> UIService["UI Service (internal)"]
    Gateway --> Backend["Backend (localhost via gateway)"]
    Gateway --> SearchUI["SearXNG Web UI (localhost via gateway)"]
    Backend --> Model["Model Backend (internal only)"]
    Backend --> Search["Search Provider"]
    Backend --> Fetcher["Fetcher / Reader"]
    Search --> Internet["Internet"]
    Fetcher --> Internet
```

## Docker Networks

- `core_internal`
  - internal bridge network for host-gateway, UI, backend, fetcher, and search-provider coordination
- `host_access`
  - non-internal bridge used only by the localhost reverse proxy so Docker Desktop can publish `127.0.0.1` ports reliably on the host
- `model_internal`
  - internal bridge network reserved for backend to model-runtime traffic
- `egress`
  - bridge network only for services that must reach the public internet

### Default network membership

- host-gateway:
  - `host_access`
  - `core_internal`
- UI:
  - `core_internal`
- backend:
  - `core_internal`
  - `model_internal`
- fetcher:
  - `core_internal`
  - `egress`
- search-provider:
  - `core_internal`
  - `egress`
- model-backend:
  - `model_internal`

## Provider Abstraction Strategy

The backend uses environment-driven provider selection:

- model:
  - `MODEL_PROVIDER`
  - `MODEL_BASE_URL`
  - `MODEL_NAME`
- search:
  - `SEARCH_PROVIDER`
  - `SEARCH_BASE_URL`
- fetch:
  - `FETCH_BASE_URL`

The current code includes:

- a localhost-only reverse proxy in front of the UI, backend, and optional standalone SearXNG host ports
- an OpenAI-compatible model adapter
- a native Ollama model adapter
- a SearXNG search adapter
- a YaCy search adapter
- a fetcher client that calls the internal fetch service
- a grounded-answer path that composes bounded source context before calling the model
- a runtime-readiness probe that distinguishes configuration from live model availability

This keeps future runtime changes small. A new model runtime should usually mean a new adapter or a new base URL, not a full backend rewrite.
The backend also no longer hard-depends on a Compose service literally named `search-provider`, so `SEARCH_BASE_URL` can point at any reachable internal or local search service that matches one of the supported adapters.
The host-facing `127.0.0.1` ports now come from the dedicated `host-gateway` service rather than from direct publishing on internal-only app containers, because Docker Desktop did not reliably expose those ports when the services were attached only to `internal: true` networks. That same gateway also provides an optional browser path to the bundled SearXNG service, so standalone search and LLM-grounded search can coexist without changing the internal network shape.

## Data Flow

### Plain prompt flow

1. UI sends a prompt to the backend.
2. UI may include a request-level model selection sourced from the runtime-advertised model list.
3. Backend validates that selection against the runtime when possible and forwards the request to the model adapter.
4. Backend returns the model response plus selection metadata to the UI.

### Grounded search flow

1. UI submits a grounding query to the backend.
2. Backend calls the configured search provider.
3. Backend selects result URLs to fetch.
4. Backend calls the fetcher service for readable page text.
5. Backend deduplicates sources, applies bounded context limits, and packages structured source metadata plus fetch errors.
6. Backend can return the grounding bundle directly or use it to call the selected model through the configured model adapter for a grounded answer.
7. UI shows the grounded answer, the selected model, the selected sources, and any per-source fetch failures.

## Why The Fetcher Is Separate

Search snippets alone are not enough. The fetcher exists so the system can retrieve, parse, and normalize article text without giving the model backend internet access.

## First Runtime Profile

The first concrete local runtime profile is `llama.cpp` in CUDA server mode, exposed as an OpenAI-compatible endpoint. The Compose profile now sets an explicit alias for the configured model name so the runtime, backend, and UI share the same stable identifier. See `docs/LLAMA_CPP_RUNTIME_PROFILE.md` for the pinned image, the default GGUF source and checksum, and the provisioning and validation flow.

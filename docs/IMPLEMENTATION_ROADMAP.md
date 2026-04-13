# Implementation Roadmap

## Project Objective

Build a reusable, privacy-first Git repository for a self-hosted local-LLM system that can be reproduced across machines with minimal manual work. The runtime stack must keep the model backend and search provider replaceable through configuration, not large code rewrites.

## Architecture Overview

The current design uses five logical boundaries:

1. a local custom UI
2. an orchestrator backend
3. a model backend on an internal non-egress network
4. a search provider or anonymizer service
5. a fetch or read service for article text extraction

Docker Compose is the initial orchestration layer. Only the UI and backend are published to `127.0.0.1`. Services that need outbound internet access join a dedicated egress-capable network. The model backend remains on an internal-only network.

## Milestones / Phases

1. `foundation-bootstrap`
   - establish repo protocol, continuity docs, architecture, security docs, Docker foundation, and initial provider scaffolding
2. `grounding-vertical-slice`
   - add a working search to fetch to grounded-context backend flow with richer error handling and a grounded-answer path
3. `local-model-integration`
   - integrate and validate one concrete local model runtime profile end to end on the target hardware
4. `ui-workbench`
   - improve the local UX for model selection, grounding visibility, and failure states
5. `provider-expansion`
   - add at least one additional model adapter and one additional search or anonymizer adapter
6. `ops-hardening`
   - tighten observability, host firewall guidance, backup, update, and maintenance flows

## Current Phase

- Active phase: `local-model-integration`
- Goal: make the first concrete local model runtime path reproducible, observable, and validated end to end on the target workstation class

## Active Branch

- `stamos/local-model-integration`

## Completed Work

- Established the project repo as a Git repository with a private GitHub remote under `StamosArhon/AnonExplo`.
- Defined the repo operating protocol in `AGENTS.md`.
- Created the continuity documents and the first architecture and security baselines.
- Added an initial Docker Compose skeleton with internal and egress network separation.
- Added minimal UI, orchestrator, and fetcher code to make the architecture concrete and reviewable.
- Added bootstrap and validation scripts and confirmed they run on the current development machine.
- Implemented a structured grounding pipeline that deduplicates search hits, selects sources, fetches article text, and reports per-source failures.
- Added a grounded-answer backend path that passes bounded fetched source text into the configured local model.
- Upgraded the local UI to show grounded answers, source status, and the exact source text slices used for grounding.
- Finalized the first concrete `llama.cpp` CUDA runtime profile and documented its provisioning flow.
- Tightened the base-stack validation to cover the grounded slice, the llama.cpp profile config, and the local Docker stack wiring.
- Added a runtime-readiness probe that distinguishes a healthy backend from a missing or misconfigured local model runtime.
- Added a model-runtime endpoint and surfaced runtime readiness in the local UI status view.
- Added a Docker healthcheck plus stable runtime aliasing for the `llama.cpp` profile so the backend, runtime, and UI share the same model identifier.
- Added `scripts/provision-default-model.ps1` to download the default GGUF into `data/models/` and verify its SHA256.
- Validated the default `QuantFactory/Qwen2.5-7B-Instruct-GGUF` Q4_K_M artifact end to end on the current development machine with the repo-managed validation flow.

## In-Progress Work

- None inside the repo contents. The remaining work is the external Git workflow to land this branch.

## Open Questions / Blockers

- The repo now validates a real GGUF load and chat probe, but it still does not record benchmark-style throughput numbers or token/sec measurements for the target hardware.
- Existing local `.env` files created before this branch may need a manual refresh of the model-runtime keys if they still contain placeholder values.
- The current SearXNG configuration is intentionally conservative and still needs deeper engine and limiter tuning in a later hardening pass.
- Host firewall guidance has been documented conceptually, but not automated.

## Decisions Made And Why

- Docker Compose is the initial orchestration layer because it is repo-managed, portable, and easy to reproduce on local machines.
- The orchestrator owns provider routing so the UI never talks directly to model, search, or fetch services.
- The model runtime is treated as an OpenAI-compatible endpoint by default because that interface keeps future runtime swaps easier.
- The fetch pipeline is a separate service so search results can be converted into readable source text without giving the model runtime internet access.
- The initial UI is a static local app with no external assets or CDN dependencies to preserve privacy and keep setup light.
- Grounded answers are built from bounded fetched source text, with per-source selection and error reporting exposed to the UI.
- `llama.cpp` CUDA server mode is the first concrete runtime profile because it fits the target hardware and keeps the backend adapter boundary clean.
- Bootstrap now generates a local SearXNG secret for new environments instead of relying on the insecure default.
- The default local model artifact is pinned by source URL, filename, and SHA256 so provisioning is explicit and repeatable.
- The backend health surface now distinguishes backend availability from model-runtime readiness so failures are easier to understand locally.
- The `llama.cpp` runtime command now sets an explicit alias matching `MODEL_NAME` to keep model discovery stable across backend, runtime, and UI.

## Security / Privacy Assumptions

- This system is for local use and is not intended for public internet exposure.
- Published ports must bind to `127.0.0.1` by default.
- The model runtime should not have outbound internet access.
- Search and fetch services are the only default services expected to need egress.
- Secrets stay in untracked local files or in the operator environment, never in Git.
- Logs should remain minimal and must not become a quiet store of prompts or fetched content.

## Validation Status

- `scripts/validate.ps1`: passed on 2026-04-13
- `scripts/validate.ps1 -RequireModelRuntime`: passed on 2026-04-13
- Validation included:
  - `docker compose config`
  - `docker compose --profile llamacpp config`
  - Docker builds for `ui`, `backend`, and `fetcher`
  - backend unit tests in the backend container
  - fetcher unit tests in the fetcher container
  - base-stack smoke validation for `ui`, `backend`, `fetcher`, and `search-provider`
  - container health and localhost port-binding inspection for the base stack
  - checksum verification for the default GGUF artifact
  - `llama.cpp` runtime startup with the pinned default GGUF
  - backend runtime-readiness probe against the live model service
  - a minimal OpenAI-compatible chat-completions probe against the live model runtime
- `scripts/bootstrap.ps1`: passed on 2026-04-13 and created the expected local `.env` plus data directories
- `scripts/provision-default-model.ps1`: passed on 2026-04-13 and downloaded the default GGUF to `data/models/`

## Exact Next Steps

1. Push `stamos/local-model-integration` and review the `main...stamos/local-model-integration` diff after confirming the validation output.
2. Merge `stamos/local-model-integration` after review and cleanup the branch per the repo workflow.
3. Improve the local workbench UX for model switching, runtime state, grounding inspection, and failure visibility on a dedicated `stamos/ui-workbench` branch.
4. Decide whether to add lightweight local benchmark reporting in a later branch or keep performance notes purely in docs.

## Handoff Notes For A Fresh Codex Thread

- Read `AGENTS.md` first.
- Then read this roadmap and `docs/INSTRUCTIONS_AND_NOTES.md`.
- The repo now includes a real grounded-answer vertical slice plus a validated `llama.cpp` runtime path with a tracked default GGUF source and checksum.
- The grounding flow is intentionally bounded and transparent: search, source selection, fetch, source packaging, and model synthesis are all visible in the UI and backend responses.
- The backend and UI now expose model-runtime readiness separately from general backend health, which future branches should preserve.
- The next implementation thread should begin with `stamos/ui-workbench` after confirming `main` is clean.

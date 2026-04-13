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

Docker Compose is the initial orchestration layer. Only the localhost gateway is published to `127.0.0.1`. Services that need outbound internet access join a dedicated egress-capable network. The model backend remains on an internal-only network.

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

- Active phase: `ops-hardening`
- Goal: tighten host-firewall guidance, validation hardening, service maintenance, and log/privacy discipline on top of the current localhost-only stack

## Active Branch

- `main`

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
- Added request-level model selection in the backend for direct chat and grounded-answer calls, validated against the runtime-advertised model catalog when available.
- Reworked the static local UI into a clearer workbench with a global model selector, runtime snapshot, provider summary, better source inspection, and more structured failure cards.
- Stabilized unsupported model-override failures so the backend returns structured selection and runtime details without falling back to a second selector call.
- Added a second model adapter for native Ollama runtimes while keeping the same orchestration contract used by the existing OpenAI-compatible runtime path.
- Added a second search adapter for YaCy so the backend can query either SearXNG or YaCy through the same grounded-search pipeline.
- Removed the backend's hard Compose dependency on a fixed `search-provider` service name so search-provider switching stays config-driven.
- Added a dedicated localhost gateway service so the UI and backend are reachable from the Windows host while the app services themselves stay on internal Docker networks.
- Tightened validation to check real host reachability on `127.0.0.1:3000` and `127.0.0.1:8000`, not just Docker's intended port-binding metadata.
- Added a localhost-only standalone SearXNG browser route through the host gateway so users can switch between direct SearXNG use and the grounded LLM workflow without exposing the search container directly.

## In-Progress Work

- None inside the repo contents. The next planned work is the `ops-hardening` milestone.

## Open Questions / Blockers

- The repo now validates a real GGUF load and chat probe, but it still does not record benchmark-style throughput numbers or token/sec measurements for the target hardware.
- Existing local `.env` files created before this branch may need a manual refresh of the model-runtime keys if they still contain placeholder values.
- The current SearXNG configuration is intentionally conservative and still needs deeper engine and limiter tuning in a later hardening pass.
- The standalone SearXNG browser route is intentionally specific to the bundled repo-managed `search-provider` service. If the backend is pointed at YaCy or another search provider, that does not automatically change the standalone browser endpoint.
- Host firewall guidance has been documented conceptually, but not automated.
- The current browser-side persistence is intentionally minimal and stores only the selected model id; there is still no prompt history or fetched-content storage policy.
- The repo now supports YaCy and native Ollama at the backend boundary, but the default validated Docker path is still the existing `llama.cpp` plus SearXNG stack rather than a fully validated alternate-provider Compose profile.
- The localhost gateway solves the current Docker Desktop host-access bug, but host-firewall and non-egress enforcement for host-facing support services still belong in the next hardening milestone.

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
- The local workbench can request a runtime-advertised model override per chat or grounded-answer call without changing the global backend configuration.
- Provider expansion is being done through adapters plus env-driven factories first, before adding more runtime-specific orchestration profiles, so the backend boundary stays cleaner than the Compose implementation details.
- Docker Desktop on this machine did not reliably expose published ports for services attached only to `internal: true` bridge networks, so host access now goes through a dedicated localhost gateway instead of direct publishing on the UI and backend containers.
- Standalone access to the bundled SearXNG web UI should use the same localhost gateway pattern as the UI and backend so the search container itself can stay unpublished on the host.

## Security / Privacy Assumptions

- This system is for local use and is not intended for public internet exposure.
- Published ports must bind to `127.0.0.1` by default.
- The model runtime should not have outbound internet access.
- Search and fetch services are the only default services expected to need egress.
- Secrets stay in untracked local files or in the operator environment, never in Git.
- Logs should remain minimal and must not become a quiet store of prompts or fetched content.

## Validation Status

- `scripts/validate.ps1`: passed on 2026-04-13 after the standalone SearXNG gateway changes
- `scripts/validate.ps1 -RequireModelRuntime`: passed on 2026-04-13 after the standalone SearXNG gateway changes
- Validation included:
  - `docker compose config`
  - `docker compose --profile llamacpp config`
  - Docker builds for `ui`, `backend`, and `fetcher`
  - backend unit tests in the backend container
  - fetcher unit tests in the fetcher container
  - base-stack smoke validation for `ui`, `backend`, `fetcher`, and `search-provider`
  - container health and localhost port-binding inspection for the base stack
  - Windows host reachability checks for the standalone SearXNG UI on the localhost gateway
  - checksum verification for the default GGUF artifact
  - `llama.cpp` runtime startup with the pinned default GGUF
  - backend runtime-readiness probe against the live model service
  - a minimal OpenAI-compatible chat-completions probe against the live model runtime
- `scripts/bootstrap.ps1`: passed on 2026-04-13 and created the expected local `.env` plus data directories
- `scripts/provision-default-model.ps1`: passed on 2026-04-13 and downloaded the default GGUF to `data/models/`
- `docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-13 with provider-expansion coverage for `openai_compatible`, `ollama`, `searxng`, and `yacy`
- `docker compose up -d --build host-gateway ui backend fetcher search-provider`: reached the UI on `http://127.0.0.1:3000`, the backend health endpoint on `http://127.0.0.1:8000/api/v1/health`, and the standalone SearXNG UI on `http://127.0.0.1:8085` from the Windows host on 2026-04-13

## Exact Next Steps

1. Start `stamos/ops-hardening` from a clean `main`.
2. Add stronger maintenance and recovery guidance, including host-firewall recommendations and service-update notes.
3. Tighten validation and smoke coverage around host access, log discipline, and service health expectations.
4. Review whether the bundled SearXNG settings need a first hardening pass without weakening the default privacy posture.

## Handoff Notes For A Fresh Codex Thread

- Read `AGENTS.md` first.
- Then read this roadmap and `docs/INSTRUCTIONS_AND_NOTES.md`.
- The repo now includes a real grounded-answer vertical slice plus a validated `llama.cpp` runtime path with a tracked default GGUF source and checksum.
- The grounding flow is intentionally bounded and transparent: search, source selection, fetch, source packaging, and model synthesis are all visible in the UI and backend responses.
- The backend and UI now expose model-runtime readiness separately from general backend health, which future branches should preserve.
- The static UI now uses backend-provided runtime and model-catalog state to drive a browser-local model selector for chat and grounded-answer requests.
- The backend now supports `openai_compatible` and `ollama` model adapters plus `searxng` and `yacy` search adapters through env-driven factories.
- The repo now supports two localhost-only browser modes at once: the main AnonExplo UI on port `3000` and the bundled standalone SearXNG UI on port `8085`, both through the same low-privilege host gateway.
- The next implementation thread should resume `stamos/ops-hardening` from a clean `main`.

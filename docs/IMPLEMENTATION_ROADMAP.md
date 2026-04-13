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
   - add a working search to fetch to grounded-context backend flow with richer error handling
3. `local-model-integration`
   - integrate and validate one concrete local model runtime profile end to end on the target hardware
4. `ui-workbench`
   - improve the local UX for model selection, grounding visibility, and failure states
5. `provider-expansion`
   - add at least one additional model adapter and one additional search or anonymizer adapter
6. `ops-hardening`
   - tighten observability, host firewall guidance, backup, update, and maintenance flows

## Current Phase

- Active phase: `foundation-bootstrap`
- Goal: create the canonical repo workflow and the first secure, reviewable stack skeleton

## Active Branch

- `stamos/foundation-bootstrap`

## Completed Work

- Established the project repo as a Git repository with a private GitHub remote under `StamosArhon/AnonExplo`.
- Defined the repo operating protocol in `AGENTS.md`.
- Created the continuity documents and the first architecture and security baselines.
- Added an initial Docker Compose skeleton with internal and egress network separation.
- Added minimal UI, orchestrator, and fetcher code to make the architecture concrete and reviewable.
- Added bootstrap and validation scripts and confirmed they run on the current development machine.

## In-Progress Work

- Commit, push, branch comparison, and merge flow for the `foundation-bootstrap` branch.

## Open Questions / Blockers

- The default model runtime profile is still an example slot. A concrete, host-validated image tag and provisioning workflow for a local model must be finalized in a later branch.
- SearXNG is scaffolded as the default search provider, but the exact production tuning for engines and cache strategy is deferred until the grounding vertical slice branch.
- Host firewall guidance has been documented conceptually, but not automated.

## Decisions Made And Why

- Docker Compose is the initial orchestration layer because it is repo-managed, portable, and easy to reproduce on local machines.
- The orchestrator owns provider routing so the UI never talks directly to model, search, or fetch services.
- The model runtime is treated as an OpenAI-compatible endpoint by default because that interface keeps future runtime swaps easier.
- The fetch pipeline is a separate service so search results can be converted into readable source text without giving the model runtime internet access.
- The initial UI is a static local app with no external assets or CDN dependencies to preserve privacy and keep setup light.

## Security / Privacy Assumptions

- This system is for local use and is not intended for public internet exposure.
- Published ports must bind to `127.0.0.1` by default.
- The model runtime should not have outbound internet access.
- Search and fetch services are the only default services expected to need egress.
- Secrets stay in untracked local files or in the operator environment, never in Git.
- Logs should remain minimal and must not become a quiet store of prompts or fetched content.

## Validation Status

- `scripts/validate.ps1`: passed on 2026-04-13
- Validation included:
  - `docker compose config`
  - Docker builds for `ui`, `backend`, and `fetcher`
  - backend unit tests in the backend container
  - fetcher unit tests in the fetcher container
- `scripts/bootstrap.ps1`: passed on 2026-04-13 and created the expected local `.env` plus data directories

## Exact Next Steps

1. Review the generated diff carefully.
2. Commit the branch with clear messages.
3. Push `stamos/foundation-bootstrap`.
4. Compare against `main`.
5. Merge to `main` if the diff still looks correct.
6. Delete the merged feature branch locally and remotely.

## Handoff Notes For A Fresh Codex Thread

- Read `AGENTS.md` first.
- Then read this roadmap and `docs/INSTRUCTIONS_AND_NOTES.md`.
- The repo currently contains a secure foundation scaffold, not a fully integrated local model stack.
- The next thread should either finish the branch workflow if it was interrupted, or start the `grounding-vertical-slice` milestone after verifying `main` is clean.

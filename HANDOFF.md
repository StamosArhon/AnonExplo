# HANDOFF

## Git Baseline

- Audit date: `2026-04-27`
- Handoff branch: `stamos/repo-handoff-sync`
- Baseline branch: `main`
- Baseline remote: `origin/main`
- Baseline sync status at audit time: `main` matched `origin/main` with no ahead or behind commits
- Baseline commit at audit time: `7fdd464` - `docs: sync roadmap after live-source merge`
- Local-only Git audit result at audit time:
  - uncommitted changes: none
  - local commits not pushed: none
  - local branches without upstreams: none
  - stashes: none

## Cleanliness

- The repo was clean before this handoff branch was created.
- This handoff branch is documentation-only and exists so the repo can carry explicit machine-migration context without merging anything by default.
- Validation note for this handoff branch:
  - `scripts/validate.ps1` was attempted on `2026-04-27`
  - it did not complete because the local Docker daemon was unavailable on this machine at the time of the handoff audit

## Latest Relevant Commit

- Baseline commit for project work: `7fdd464` - `docs: sync roadmap after live-source merge`
- Most recent merged feature area before this handoff branch:
  - `889ac49` - `Tune live-source fetch resilience`

## Project Status

- Current phase from `docs/IMPLEMENTATION_ROADMAP.md`: `post-roadmap-enhancement`
- Current baseline status:
  - the core roadmap baseline is complete
  - `main` is the stable working baseline
  - the latest merged enhancement improved live-source fetch resilience, partial oversized-page extraction, long-document head-and-tail retention, and current-events source selection
- Current notable open issue:
  - multi-part grounded answers on fast-moving current-events topics can still under-answer the second clause even when the fetched source set contains partial supporting material

## Exact Next Recommended Step

1. On the next machine, clone the repo and fetch this handoff branch if you want the exact migration notes preserved in Git before any merge decision.
2. Restore local machine state that is intentionally not stored in Git:
   - copy `.env` out of band, or recreate it from `.env.example`
   - copy `data/models/Qwen2.5-7B-Instruct.Q4_K_M.gguf` out of band, or rerun `scripts/provision-default-model.ps1`
3. Run the standard validation path on the next machine.
4. Start the next recommended feature branch from `main`:
   - `stamos/multi-part-answer-coverage`
   - goal: improve grounded answers for compound live-current-events questions so both clauses are answered more consistently from fetched evidence

## Local Tooling Assumptions For The Next Machine

- Windows plus PowerShell is the current scripted environment.
- Docker Desktop with Docker Compose support is assumed.
- Docker Desktop must actually be running before `scripts/validate.ps1` or the Compose-based startup commands will work.
- The default validated runtime path assumes access to an NVIDIA-capable local environment for the `llama.cpp` CUDA profile.
- The repo-managed commands to know first:
  - `powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/provision-default-model.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime`
  - `powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1`
- These local artifacts do not travel through Git:
  - `.env`
  - `data/models/*`
  - `data/searxng-cache/*`
  - Docker images, containers, and local volumes
  - browser-local direct-chat history, selected-model state, and saved UI instruction text

## Immediate Practical Notes

- `FETCHER_CLIENT_TIMEOUT_SECONDS` should stay slightly higher than `FETCH_REQUEST_TIMEOUT_SECONDS`.
- Wikimedia support remains opt-in and requires both:
  - `FETCH_WIKIMEDIA_API_ENABLED=true`
  - a real `FETCH_WIKIMEDIA_API_USER_AGENT` in `.env`
- Standalone SearXNG access is still routed through the localhost gateway, not by publishing the search container directly.

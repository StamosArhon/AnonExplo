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
- Grounded-answer transcripts, fetched source details, and fetch-inspector output must stay transient unless a later milestone adds a privacy-reviewed storage design first.
- Keep `Direct Chat` and `Grounded Answer` semantically explicit in both code and copy. Direct Chat is model only; Grounded Answer is the search plus fetch plus model workflow.
- Request-level model selection should stay bounded to runtime-advertised models and should not mutate the backend's configured default model.
- Do not reintroduce a backend orchestration dependency on one hard-coded search service name; provider switching should remain env-driven at the backend boundary.
- Keep the host-facing UI and backend access path behind the dedicated localhost gateway unless there is a documented reason to publish app containers directly.
- If the bundled SearXNG web UI is exposed for standalone use, route it through the same localhost gateway rather than publishing the search container directly.
- Future branches should prefer expanding functionality through adapters and configuration rather than adding direct service-to-service coupling.
- `scripts/validate.ps1` now enforces the intended Compose hardening model, including localhost-only publication, expected network membership, digest-pinned third-party images, and local-only CORS origins.

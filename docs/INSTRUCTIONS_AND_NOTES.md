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

## Branch / Merge Workflow

- Always use `stamos/<branch-name>`.
- Keep branches narrow.
- After merge, delete the completed working branch locally and remotely.
- If a branch changes recurring repo rules, update `AGENTS.md` in the same branch.

## Practical Notes

- The first branch intentionally keeps the UI static and lightweight to avoid introducing a frontend toolchain before the architecture is stable.
- The current model slot is a concrete `llama.cpp` CUDA profile, but the backend remains adapter-driven and should not be coupled to that runtime.
- Future branches should prefer expanding functionality through adapters and configuration rather than adding direct service-to-service coupling.

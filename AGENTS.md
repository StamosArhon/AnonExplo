# AGENTS.md

This repository is the canonical source of truth for the AnonExplo project. Do not rely on chat memory for continuity. Durable decisions, validation status, security assumptions, and next steps must be written into the repo.

## Read First

Every new Codex thread must read these files in order before making changes:

1. `AGENTS.md`
2. `docs/IMPLEMENTATION_ROADMAP.md`
3. `docs/INSTRUCTIONS_AND_NOTES.md`
4. `docs/ARCHITECTURE.md`
5. `docs/SECURITY_PRIVACY.md`

If the task touches local model provisioning or runtime settings, also read `docs/LLAMA_CPP_RUNTIME_PROFILE.md`.

## Branching Rules

- Every implementation step, milestone, or tightly scoped change must use a fresh branch named exactly `stamos/<branch-name>`.
- Do not keep working on a stale branch after its scope is complete.
- Keep branches small, reviewable, and single-purpose.

## Workflow Rules

For each branch, complete this workflow before stopping:

1. Update `AGENTS.md` if repo operating rules changed.
2. Update `docs/IMPLEMENTATION_ROADMAP.md`.
3. Update `docs/INSTRUCTIONS_AND_NOTES.md` if recurring rules or important notes changed.
4. Run the relevant checks.
5. Commit with clear messages.
6. Push the branch to `origin`.
7. Compare the branch against `main` and review the diff carefully.
8. Merge into `main` only when the branch is secure, validated, and genuinely ready.
9. Delete the completed working branch locally and remotely after merge.
10. Stop and prompt the user with a short summary, architectural or operational changes, the next recommended milestone, and a direct question asking whether to proceed.

If a remote is missing or remote operations fail, record that explicitly in the roadmap and do not pretend push, merge, or cleanup happened.

## Validation Requirements

- Run `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1` before declaring a branch ready.
- At minimum, validation must include:
  - `docker compose config`
  - Docker image builds for repo-managed services
  - Unit or smoke tests for changed app code
- If a validation step is skipped or fails, record that in `docs/IMPLEMENTATION_ROADMAP.md`.

## Security And Privacy Guardrails

- Default to localhost-only exposure for UI and orchestrator ports.
- Keep the model runtime off any egress-capable Docker network unless there is a documented reason not to.
- Only services that truly need outbound internet access may join the egress network.
- Do not add telemetry, remote fonts, CDNs, analytics, or third-party runtime calls unless explicitly approved and documented.
- Do not commit secrets, tokens, model weights, browser histories, prompts, fetched pages, or user data.
- Prefer non-root containers, dropped Linux capabilities, and `no-new-privileges` where practical.
- Treat model acquisition and updates as explicit provisioning steps, not ad hoc runtime downloads.

## Documentation Rules

- `docs/IMPLEMENTATION_ROADMAP.md` is the living continuity and handoff document. Update it whenever architecture changes, meaningful progress is made, a branch ends, or blockers appear.
- `docs/INSTRUCTIONS_AND_NOTES.md` stores persistent implementation rules and practical notes that future threads must not forget.
- `README.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY_PRIVACY.md` should stay aligned with the current repo state.

## Repo Conventions

- AnonExplo is a SearXNG browser-search product, not an LLM product. The native
  SearXNG UI at `127.0.0.1:8085` is the user interface; Brave uses
  `/search?q=%s` directly. Preserve that endpoint and VPN-only search egress.
- Do not add a replacement UI, local model, query history, or hidden query
  expansion without a demonstrated need and a separately scoped decision.
- Tune browser results in SearXNG, not the legacy backend. Preserve engine
  cooldowns and use synthetic manual tests rather than user history.
- Favor config-driven provider selection instead of hard-coding one model backend or one search provider.
- Only the legacy chatbot UI talks to the orchestrator; native SearXNG does not.
- Search and page-fetching remain separate concerns even when the backend offers a combined grounding endpoint.
- Prefer exact dependency versions where practical.
- Use repo-managed scripts for repeatable setup and validation.

## Useful Commands

- Start the configured private browser search: `powershell -ExecutionPolicy Bypass -File scripts/start-proton-search.ps1`
- Check VPN search isolation: `powershell -ExecutionPolicy Bypass -File scripts/check-proton-search.ps1`
- Manual synthetic browser benchmark: `powershell -ExecutionPolicy Bypass -File scripts/test-browser-search.ps1`
- Bootstrap local files: `powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1`
- Check the running local stack: `powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1`
- Provision the default GGUF locally: `powershell -ExecutionPolicy Bypass -File scripts/provision-default-model.ps1`
- Validate the branch: `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1`
- Validate with the full model-runtime probe: `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime`
- Start the base stack: `docker compose up --build host-gateway ui backend fetcher search-provider`
- Start the pinned llama.cpp model profile: `docker compose --profile llamacpp up -d model-backend`

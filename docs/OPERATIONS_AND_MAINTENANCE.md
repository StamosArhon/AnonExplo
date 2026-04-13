# Operations And Maintenance

## Purpose

This guide covers the practical operator path for keeping the local AnonExplo stack healthy on a single workstation. It is intentionally focused on local-only usage, repeatable updates, and privacy-preserving troubleshooting.

## Daily Health Check

Use the lightweight operational check when the stack is already running:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1
```

If you also expect the local model runtime to be ready:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1 -RequireModelRuntime
```

That script checks:

- the UI on `127.0.0.1:3000`
- the backend health endpoint on `127.0.0.1:8000`
- the standalone SearXNG UI on `127.0.0.1:8085`
- the backend-reported model runtime state
- `docker compose ps`

## Start And Stop

Start the pinned local model runtime:

```powershell
docker compose --profile llamacpp up -d model-backend
```

Start the rest of the local stack:

```powershell
docker compose up -d host-gateway ui backend fetcher search-provider
```

Stop everything:

```powershell
docker compose --profile llamacpp down --remove-orphans
```

## Safe Update Workflow

When the repo or pinned images change, prefer this order:

1. Review `README.md`, `.env.example`, and `docs/LLAMA_CPP_RUNTIME_PROFILE.md` for changed settings.
2. Refresh `.env` deliberately if new keys were added.
3. Pull pinned third-party images:

   ```powershell
   docker compose pull host-gateway search-provider model-backend
   ```

4. Rebuild repo-managed services:

   ```powershell
   docker compose build --pull ui backend fetcher
   ```

5. Run the full validation path:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime
   ```

6. Start the stack again and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1 -RequireModelRuntime
   ```

## Recovery Notes

### UI reachable but backend degraded

This usually means the local model runtime is still loading or failed after startup.

Recommended sequence:

1. `powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1 -RequireModelRuntime`
2. `docker compose ps`
3. `docker compose logs --tail=80 model-backend backend`

If `model-backend` is still on `health: starting`, wait and re-run the ops check before making deeper changes.

### Standalone SearXNG works but grounded answers fail

That usually means the failure is in the backend orchestration or the fetch layer, not in the browser route itself.

Inspect:

```powershell
docker compose logs --tail=80 backend fetcher search-provider
```

Then re-run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
```

### Host entrypoints are unreachable

Inspect the gateway first:

```powershell
docker compose logs --tail=80 host-gateway ui backend search-provider
```

Then confirm the expected localhost-only entrypoints:

- `http://127.0.0.1:3000`
- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8085`

## Windows Host Firewall Guidance

The primary security boundary for this repo is still the Docker network design, not a promise that Windows Defender Firewall can replace per-container policy on Docker Desktop.

Recommended baseline:

- keep published ports bound to `127.0.0.1` only
- do not add broad inbound allow rules for Docker Desktop or the localhost gateway
- do not rebind the UI, backend, or standalone SearXNG ports to `0.0.0.0` unless you are deliberately changing the threat model
- if you change any host-facing port or bind address, rerun `scripts/validate.ps1` before treating the stack as ready again

Important limitation:

- on Docker Desktop and WSL2, outbound restriction is not reliably enforced by Windows Firewall alone at the individual container level
- keep Docker internal-network and egress-network separation as the primary control for limiting internet reach

## Log Discipline

Repo-managed services now keep routine logging quieter where practical:

- the UI server suppresses routine request logs
- backend and fetcher `uvicorn` access logs are disabled
- the localhost gateway disables routine access logging and keeps only warning-level error logging

Operational guidance:

- inspect logs ad hoc with `docker compose logs --tail=80 <service>`
- avoid redirecting prompts, grounded source text, or fetched article bodies into files under the repo
- if temporary debug logging is introduced, remove it before merging

## Backups And Local State

Important local assets to protect:

- `.env`
- `data/models/`
- optional `data/searxng-cache/`

Browser-local direct chat history and saved instruction text are stored in local storage inside the browser profile, not inside the repo. They are not covered by repo-level filesystem backups unless you back up the browser profile separately.

# Browser Search Integration

## Purpose

This runbook documents the Windows host pipeline used to make browser address-bar search use the repo-managed standalone SearXNG route, with an automatic DuckDuckGo fallback when the local SearXNG route is unavailable.

The setup is intentionally machine-local. It creates Windows startup entries and helper scripts under the user's local profile, but it does not commit browser profiles, search history, prompts, fetched pages, cookies, or secrets into the repo.

## One-Command Setup

The repo now includes a Windows setup script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-browser-search.ps1
```

Prerequisites:

- Docker Desktop
- Node.js with global `fetch` support for the redirector
- Node.js 22 or newer for browser profile automation, because the Chromium DevTools helper uses global `WebSocket`

Recommended fully automatic run when Brave or Helium may already be open:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-browser-search.ps1 -ForceCloseBrowsers
```

The script:

1. Writes the machine-local helper files under `%LOCALAPPDATA%\AnonExplo\search-fallback`.
2. Uses hidden `wscript.exe` launchers so the redirector and stack starter do not show terminal windows at logon.
3. Registers the startup task and redirector task when Task Scheduler permissions allow it.
4. Repairs existing matching tasks to use hidden launchers when direct scheduled-task replacement is denied.
5. Falls back to current-user Startup folder launchers if scheduled-task creation is unavailable and no existing matching tasks are present.
6. Repoints the current user's Docker Desktop logon entry to a hidden `docker desktop start --detach` launcher when that entry directly launches `Docker Desktop.exe`.
7. Discovers Brave and Helium profile directories from their local browser data.
8. Configures each discovered Chromium profile to use `http://127.0.0.1:8095/search?q=%s`.
9. Verifies each configured profile reports `AnonExplo SearXNG (Default)`.

Useful options:

- `-SkipBrowserConfiguration`: create or refresh the local helper files and startup entries without touching browser profiles.
- `-ForceCloseBrowsers`: close matching Brave or Helium processes before profile automation.
- `-NoDuckDuckGoFallback`: make the redirector return a local `503` instead of falling back to DuckDuckGo.
- `-SkipBrave` or `-SkipHelium`: skip one browser family.
- `-NoStartNow`: register startup behavior without starting the helpers immediately.
- `-NoDockerDesktopStart`: keep the AnonExplo startup helper from starting Docker Desktop if Docker is not already ready.
- `-SkipDockerRunEntryRepair`: leave the current user's Docker Desktop logon entry unchanged.
- `-SkipTaskRegistration`: write helper files only.
- `-NoStartupFolderFallback`: require scheduled-task registration and fail instead of creating Startup folder launchers.

## Target Behavior

- Docker Desktop starts at Windows login if it is not already running.
- The AnonExplo base stack starts automatically:
  - `host-gateway`
  - `ui`
  - `backend`
  - `fetcher`
  - `search-provider`
- The standalone SearXNG UI remains reachable through the localhost gateway at `http://127.0.0.1:8085`.
- A local fallback redirector listens on `http://127.0.0.1:8095/search?q=...`.
- Browsers use the redirector, not SearXNG directly, as their default search engine:
  - search engine name: `AnonExplo SearXNG`
  - keyword: `searxng.local`
  - browser search URL: `http://127.0.0.1:8095/search?q=%s`
- When SearXNG is healthy, the redirector sends searches to:
  - `http://127.0.0.1:8085/search?q=...`
- When SearXNG is down or the gateway is unavailable, the redirector sends searches to:
  - `https://duckduckgo.com/?q=...`

Important privacy note: DuckDuckGo fallback intentionally sends the query to DuckDuckGo only when the local route is unavailable. If a device must never send fallback queries to an external search engine, change the redirector behavior before configuring browser defaults.

## Local Components

Use these names for consistency across machines:

- Windows scheduled task: `AnonExplo SearXNG Startup`
- Windows scheduled task: `AnonExplo Search Fallback Redirector`
- Local helper directory: `%LOCALAPPDATA%\AnonExplo\search-fallback`
- Redirector script: `%LOCALAPPDATA%\AnonExplo\search-fallback\search-fallback.js`
- Browser automation helper: `%LOCALAPPDATA%\AnonExplo\search-fallback\configure-chromium-search.js`
- Startup helper: `%LOCALAPPDATA%\AnonExplo\search-fallback\start-anonexplo-searxng.ps1`
- Hidden startup launcher: `%LOCALAPPDATA%\AnonExplo\search-fallback\start-anonexplo-searxng.vbs`
- Hidden redirector launcher: `%LOCALAPPDATA%\AnonExplo\search-fallback\start-search-fallback.vbs`
- Hidden Docker Desktop launcher: `%LOCALAPPDATA%\AnonExplo\search-fallback\start-docker-desktop-background.vbs`

The helper scripts are generated from `scripts/setup-browser-search.ps1` and remain machine-local operational files. Do not commit generated helper files, browser profiles, browser data, or Task Scheduler exports.

## Startup Task

The startup task should run at user logon with a hidden PowerShell action.

The action should:

1. Set the repo path for that device.
2. Start Docker Desktop with `docker desktop start --detach` if `docker info` fails, unless setup was run with `-NoDockerDesktopStart`.
3. Wait for Docker to become ready.
4. If `127.0.0.1:3000` is already occupied, set `UI_PORT=3001` for that run.
5. If `127.0.0.1:8000` is already occupied, set `BACKEND_PORT=8001` for that run.
6. Run:

   ```powershell
   docker compose up -d host-gateway ui backend fetcher search-provider
   ```

The task does not need to start the model runtime unless the device should also have local model inference ready at login. The browser search integration only requires the gateway and `search-provider`.

## Redirector Task

The fallback redirector should be a small local Node.js service started by Task Scheduler or a Startup folder launcher at user logon. It must be launched through the hidden VBS wrapper, not directly through `node.exe`, so closing a visible terminal can never stop browser search.

Behavior:

1. Listen only on `127.0.0.1:8095`.
2. Accept `/search?q=...`.
3. Check `http://127.0.0.1:8085/` with a short timeout.
4. If healthy, return `302` to `http://127.0.0.1:8085/search?q=...`.
5. If unhealthy, return `302` to `https://duckduckgo.com/?q=...`.
6. Set `Cache-Control: no-store`.

Verification:

```powershell
Get-NetTCPConnection -LocalPort 8095,8085 -State Listen
curl.exe -s -I "http://127.0.0.1:8095/search?q=anonexplo-check"
```

The expected healthy redirect contains:

```text
Location: http://127.0.0.1:8085/search?q=anonexplo-check
```

Optional fallback verification:

1. Temporarily stop only the localhost gateway.
2. Re-run the redirector check.
3. Confirm the `Location` header points to DuckDuckGo.
4. Restart the gateway immediately.

```powershell
docker compose stop host-gateway
curl.exe -s -I "http://127.0.0.1:8095/search?q=fallback-check"
docker compose up -d host-gateway
```

The expected fallback redirect contains:

```text
Location: https://duckduckgo.com/?q=fallback-check
```

## Browser Profile Discovery

Configure every real Chromium profile in the target browsers.

Known Windows paths from the validated setup:

- Brave user data:
  - `%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data`
- Brave executable:
  - `%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe`
- Helium user data:
  - `%LOCALAPPDATA%\imput\Helium\User Data`
- Helium executable:
  - `%LOCALAPPDATA%\imput\Helium\Application\chrome.exe`

Profile directories are usually `Default` plus `Profile N`.

Discovery rules:

1. Read each browser's `Local State` file when possible.
2. Use `profile.info_cache` to map profile directories to human-readable names.
3. Also inspect `Default` and `Profile *` directories that contain a `Preferences` file, because some profiles can exist even when the display-name cache is incomplete.
4. Do not read, export, or commit browser history, cookies, sessions, login data, or web data.

On the validated workstation, the target profiles were:

- Helium:
  - `Default` / Stamos
  - `Profile 1` / FactReview
  - `Profile 2` / The Mad Scientist
- Brave:
  - `Profile 4` / The Mad Scientist
  - `Profile 6` / FactReview
  - `Profile 7` / Stamos
  - `Default`, if present and intended for use

Other devices may have different profile numbers, so discover them instead of hard-coding these directories.

## Browser Configuration Method

Prefer Chrome DevTools Protocol automation over direct file edits.

For each browser profile:

1. Close that browser first when practical.
2. Launch the browser with:

   ```text
   --remote-debugging-port=<unique-port>
   --user-data-dir=<browser-user-data-dir>
   --profile-directory=<profile-directory>
   --no-first-run
   --no-default-browser-check
   chrome://settings/searchEngines
   ```

3. In the settings page, locate the `settings-search-engines-page` component.
4. Add or update the search engine:
   - name: `AnonExplo SearXNG`
   - keyword: `searxng.local`
   - URL: `http://127.0.0.1:8095/search?q=%s`
5. Re-read the browser search-engine list.
6. Locate the row for `AnonExplo SearXNG`.
7. Invoke the row-level default action, equivalent to clicking `Make default`.
8. Re-read the search-engine list and verify the display name is `AnonExplo SearXNG (Default)`.
9. Close the automation browser instance through CDP.

Important Brave gotcha: do not rely only on the raw `setDefaultSearchEngine(...)` browser-proxy method. During the validated setup, Brave accepted the engine but left Google as the real top-level default for the Stamos profile until the automation invoked the row-level `settings-search-engine-entry.onMakeDefaultClick_()` action. Future automation should verify the final list, not just assume the setter worked.

## Verification Checklist

After configuring all profiles:

1. Confirm SearXNG is reachable:

   ```powershell
   curl.exe -s -I "http://127.0.0.1:8085/"
   ```

2. Confirm the redirector is reachable:

   ```powershell
   curl.exe -s -I "http://127.0.0.1:8095/search?q=verify"
   ```

3. Confirm the healthy redirect points at SearXNG:

   ```text
   Location: http://127.0.0.1:8085/search?q=verify
   ```

4. Confirm every intended browser profile reports:

   ```text
   AnonExplo SearXNG (Default)
   ```

5. Manually open each browser profile and search from the address bar.

6. If one profile still uses Google, rerun the CDP automation for that profile and specifically verify the row-level default action.

## Troubleshooting

### The browser shows AnonExplo SearXNG but still searches Google

The engine was added but not promoted to the real default. Use the settings-row `Make default` path and verify `AnonExplo SearXNG (Default)` in the browser's search-engine list.

### Searches show a local error page

The browser is probably pointed directly at `127.0.0.1:8085` instead of the redirector. Change the browser default URL to:

```text
http://127.0.0.1:8095/search?q=%s
```

### A terminal window appears at login

Rerun the setup script without browser profile changes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-browser-search.ps1 -SkipBrowserConfiguration
```

Then confirm both scheduled tasks use `wscript.exe` actions:

```powershell
Get-ScheduledTask -TaskName "AnonExplo SearXNG Startup","AnonExplo Search Fallback Redirector" |
  Select-Object TaskName,Actions
```

The redirector must not be launched directly as `node.exe`.

### Docker Desktop opens in the foreground at login

Rerun:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-browser-search.ps1 -SkipBrowserConfiguration
```

The setup repairs the current user's Docker Desktop logon entry when it directly launches `Docker Desktop.exe`, replacing it with a hidden launcher that calls:

```powershell
docker desktop start --detach
```

### Searches go to DuckDuckGo even though Docker is running

Check the gateway and search-provider:

```powershell
docker compose ps host-gateway search-provider
docker compose logs --tail=80 host-gateway search-provider
curl.exe -s -I "http://127.0.0.1:8085/"
```

### Port 3000 or 8000 is occupied

The startup task may set `UI_PORT=3001` or `BACKEND_PORT=8001` for that run. This is acceptable for the browser search pipeline because SearXNG still uses the gateway route on `127.0.0.1:8085`.

If `scripts/validate.ps1` needs to run while another local app is using port `3000`, set the process-level override first:

```powershell
$env:UI_PORT = "3001"
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
```

### Port 8085 or 8095 is occupied

Do not silently reuse a different port without also updating this runbook, the redirector, and every browser profile. The current convention is:

- `8085`: standalone SearXNG through AnonExplo's localhost gateway
- `8095`: local browser-search fallback redirector

## Prompt For Codex On Another Device

Use a prompt like this after cloning the repo on the target Windows machine:

```text
Read AGENTS.md and docs/BROWSER_SEARCH_INTEGRATION.md. Run scripts/setup-browser-search.ps1 to configure this Windows device so AnonExplo's SearXNG browser route starts at login, create the localhost search fallback redirector, and set the redirector as the default search engine for every Helium and Brave Chromium profile. Discover profile directories from this machine; do not hard-code profile numbers from another machine. Use http://127.0.0.1:8095/search?q=%s as the browser search URL, verify each profile reports AnonExplo SearXNG (Default), and verify the redirector sends healthy searches to http://127.0.0.1:8085/search?q=... with DuckDuckGo fallback only when the local route is down. Do not commit browser profiles, generated helper scripts, search history, cookies, prompts, fetched pages, or secrets.
```

param(
    [switch]$SkipBrave,
    [switch]$SkipHelium,
    [switch]$SkipBrowserConfiguration,
    [switch]$ForceCloseBrowsers,
    [switch]$SkipTaskRegistration,
    [switch]$NoStartupFolderFallback,
    [switch]$NoStartNow,
    [switch]$NoDockerDesktopStart,
    [switch]$SkipDockerRunEntryRepair,
    [switch]$NoDuckDuckGoFallback,
    [int]$RedirectorPort = 8095,
    [int]$SearxngPort = 8085,
    [int]$PreferredUiPort = 3000,
    [int]$FallbackUiPort = 3001,
    [int]$PreferredBackendPort = 8000,
    [int]$FallbackBackendPort = 8001,
    [int]$CdpPortBase = 9320,
    [string]$BraveExe = "",
    [string]$BraveUserDataDir = "",
    [string]$HeliumExe = "",
    [string]$HeliumUserDataDir = ""
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$helperDir = Join-Path $env:LOCALAPPDATA "AnonExplo\search-fallback"
$redirectorScript = Join-Path $helperDir "search-fallback.js"
$startupScript = Join-Path $helperDir "start-anonexplo-searxng.ps1"
$startupLauncher = Join-Path $helperDir "start-anonexplo-searxng.vbs"
$redirectorLauncher = Join-Path $helperDir "start-search-fallback.vbs"
$dockerDesktopLauncher = Join-Path $helperDir "start-docker-desktop-background.vbs"
$configureScript = Join-Path $helperDir "configure-chromium-search.js"

$searchName = "AnonExplo SearXNG"
$searchKeyword = "searxng.local"
$browserSearchUrl = "http://127.0.0.1:$RedirectorPort/search?q=%s"
$searxngBaseUrl = "http://127.0.0.1:$SearxngPort"
$duckDuckGoBaseUrl = "https://duckduckgo.com/"

$startupTaskName = "AnonExplo SearXNG Startup"
$redirectorTaskName = "AnonExplo Search Fallback Redirector"
$startupLaunchMode = "None"

function Resolve-FirstExistingPath {
    param([string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Test-LocalListenPort {
    param([int]$Port)

    return [bool](Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-NodePath {
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $node) {
        throw "Node.js was not found on PATH. Install Node.js before running browser search setup."
    }

    return $node.Source
}

function Assert-NodeCapabilities {
    param(
        [string]$NodePath,
        [bool]$NeedsWebSocket
    )

    $probe = "if (typeof fetch !== 'function') process.exit(2); if ('$NeedsWebSocket' === 'True' && typeof WebSocket !== 'function') process.exit(3);"
    & $NodePath -e $probe
    if ($LASTEXITCODE -eq 2) {
        throw "The detected Node.js runtime does not provide global fetch(). Install a current Node.js release."
    }
    if ($LASTEXITCODE -eq 3) {
        throw "Browser automation needs a Node.js runtime with global WebSocket support. Install Node.js 22 or newer."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to verify Node.js runtime capabilities."
    }
}

function Write-LocalHelperFiles {
    param([string]$NodePath)

    New-Item -ItemType Directory -Force -Path $helperDir | Out-Null

    $allowFallback = if ($NoDuckDuckGoFallback) { "false" } else { "true" }
    $fallbackBase = if ($NoDuckDuckGoFallback) { "" } else { $duckDuckGoBaseUrl }

    $redirectorTemplate = @'
const http = require("node:http");

const LISTEN_HOST = "127.0.0.1";
const LISTEN_PORT = __REDIRECTOR_PORT__;
const SEARXNG_BASE_URL = "__SEARXNG_BASE_URL__";
const ALLOW_EXTERNAL_FALLBACK = __ALLOW_EXTERNAL_FALLBACK__;
const FALLBACK_BASE_URL = "__FALLBACK_BASE_URL__";

function buildSearchUrl(baseUrl, query) {
  const url = new URL("/search", baseUrl);
  url.searchParams.set("q", query);
  return url.toString();
}

function buildDuckDuckGoUrl(query) {
  const url = new URL(FALLBACK_BASE_URL);
  url.searchParams.set("q", query);
  return url.toString();
}

async function isSearxngHealthy() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1200);
  try {
    const response = await fetch(`${SEARXNG_BASE_URL}/`, {
      method: "GET",
      redirect: "manual",
      signal: controller.signal,
    });
    return response.status >= 200 && response.status < 500;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

function sendRedirect(response, location) {
  response.writeHead(302, {
    Location: location,
    "Cache-Control": "no-store",
    "Content-Type": "text/plain; charset=utf-8",
  });
  response.end(`Redirecting to ${location}\n`);
}

const server = http.createServer(async (request, response) => {
  const requestUrl = new URL(request.url, `http://${LISTEN_HOST}:${LISTEN_PORT}`);

  if (requestUrl.pathname === "/health") {
    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Type": "text/plain; charset=utf-8",
    });
    response.end("ok\n");
    return;
  }

  if (requestUrl.pathname !== "/search") {
    response.writeHead(404, {
      "Cache-Control": "no-store",
      "Content-Type": "text/plain; charset=utf-8",
    });
    response.end("not found\n");
    return;
  }

  const query = requestUrl.searchParams.get("q") || "";
  if (await isSearxngHealthy()) {
    sendRedirect(response, buildSearchUrl(SEARXNG_BASE_URL, query));
    return;
  }

  if (ALLOW_EXTERNAL_FALLBACK) {
    sendRedirect(response, buildDuckDuckGoUrl(query));
    return;
  }

  response.writeHead(503, {
    "Cache-Control": "no-store",
    "Content-Type": "text/plain; charset=utf-8",
  });
  response.end("Local SearXNG is unavailable and external fallback is disabled.\n");
});

server.listen(LISTEN_PORT, LISTEN_HOST, () => {
  console.log(`AnonExplo search fallback redirector listening on http://${LISTEN_HOST}:${LISTEN_PORT}`);
});
'@

    $redirector = $redirectorTemplate.
        Replace("__REDIRECTOR_PORT__", [string]$RedirectorPort).
        Replace("__SEARXNG_BASE_URL__", $searxngBaseUrl).
        Replace("__ALLOW_EXTERNAL_FALLBACK__", $allowFallback).
        Replace("__FALLBACK_BASE_URL__", $fallbackBase)
    Set-Content -LiteralPath $redirectorScript -Value $redirector -Encoding UTF8

    $escapedRoot = $root.Replace("'", "''")
    $startDockerIfNeeded = if ($NoDockerDesktopStart) { '$false' } else { '$true' }
    $startupTemplate = @'
$ErrorActionPreference = "SilentlyContinue"

$repo = '__REPO_PATH__'
$startDockerIfNeeded = __START_DOCKER_IF_NEEDED__

function Test-LocalListenPort {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Set-PortOrFallback {
    param(
        [string]$Name,
        [int]$Preferred,
        [int]$Fallback
    )

    if (Test-LocalListenPort -Port $Preferred) {
        if (Test-LocalListenPort -Port $Fallback) {
            exit 20
        }
        [Environment]::SetEnvironmentVariable($Name, [string]$Fallback, "Process")
        return
    }

    [Environment]::SetEnvironmentVariable($Name, [string]$Preferred, "Process")
}

& docker info *> $null
if ($LASTEXITCODE -ne 0 -and $startDockerIfNeeded) {
    & docker desktop start --detach --timeout 120 *> $null
}

$dockerReady = $false
for ($i = 0; $i -lt 72; $i++) {
    & docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }
    Start-Sleep -Seconds 5
}

if (-not $dockerReady) {
    exit 10
}

Set-PortOrFallback -Name "UI_PORT" -Preferred __PREFERRED_UI_PORT__ -Fallback __FALLBACK_UI_PORT__
Set-PortOrFallback -Name "BACKEND_PORT" -Preferred __PREFERRED_BACKEND_PORT__ -Fallback __FALLBACK_BACKEND_PORT__
[Environment]::SetEnvironmentVariable("SEARXNG_UI_PORT", "__SEARXNG_PORT__", "Process")

Set-Location -LiteralPath $repo
& docker compose up -d host-gateway ui backend fetcher search-provider
exit $LASTEXITCODE
'@

    $startup = $startupTemplate `
        -replace "__REPO_PATH__", $escapedRoot `
        -replace "__PREFERRED_UI_PORT__", [string]$PreferredUiPort `
        -replace "__FALLBACK_UI_PORT__", [string]$FallbackUiPort `
        -replace "__PREFERRED_BACKEND_PORT__", [string]$PreferredBackendPort `
        -replace "__FALLBACK_BACKEND_PORT__", [string]$FallbackBackendPort `
        -replace "__SEARXNG_PORT__", [string]$SearxngPort `
        -replace "__START_DOCKER_IF_NEEDED__", $startDockerIfNeeded
    Set-Content -LiteralPath $startupScript -Value $startup -Encoding UTF8

    $escapedStartupScript = $startupScript.Replace("""", """""")
    $escapedNodePath = $NodePath.Replace("""", """""")
    $escapedRedirectorScript = $redirectorScript.Replace("""", """""")

    $startupLauncherContent = @"
Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""$escapedStartupScript""", 0, False
"@

    $redirectorLauncherContent = @"
Set shell = CreateObject("WScript.Shell")
shell.Run """$escapedNodePath"" ""$escapedRedirectorScript""", 0, False
"@

    Set-Content -LiteralPath $startupLauncher -Value $startupLauncherContent -Encoding ASCII
    Set-Content -LiteralPath $redirectorLauncher -Value $redirectorLauncherContent -Encoding ASCII

    $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($dockerCommand) {
        $escapedDockerPath = $dockerCommand.Source.Replace("""", """""")
        $dockerLauncherContent = @"
Set shell = CreateObject("WScript.Shell")
shell.Run """$escapedDockerPath"" desktop start --detach", 0, False
"@
        Set-Content -LiteralPath $dockerDesktopLauncher -Value $dockerLauncherContent -Encoding ASCII
    }

    $configureHelper = @'
const { spawn } = require("node:child_process");

const [exe, userDataDir, profileDirectory, portRaw, searchUrl, name, keyword] = process.argv.slice(2);
const port = Number(portRaw);
const oldUrl = `http://127.0.0.1:8085/search?q=%s`;

if (!exe || !userDataDir || !profileDirectory || !Number.isInteger(port) || !searchUrl || !name || !keyword) {
  console.error("Usage: node configure-chromium-search.js <exe> <userDataDir> <profileDirectory> <port> <searchUrl> <name> <keyword>");
  process.exit(2);
}

if (typeof WebSocket !== "function") {
  console.error("This helper requires a Node.js runtime with global WebSocket support.");
  process.exit(2);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

async function waitForCdp() {
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    try {
      return await fetchJson(`http://127.0.0.1:${port}/json/version`);
    } catch {
      await sleep(500);
    }
  }
  throw new Error(`CDP did not become available on port ${port}`);
}

async function cdp(webSocketDebuggerUrl) {
  const ws = new WebSocket(webSocketDebuggerUrl);
  let seq = 1;
  const pending = new Map();

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
    }
  };

  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });

  return {
    send(method, params = {}) {
      const id = seq++;
      ws.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve) => pending.set(id, resolve));
    },
    close() {
      ws.close();
    },
  };
}

function configureExpression() {
  return `(async () => {
    const NAME = ${JSON.stringify(name)};
    const KEYWORD = ${JSON.stringify(keyword)};
    const URL = ${JSON.stringify(searchUrl)};
    const OLD_URL = ${JSON.stringify(oldUrl)};

    function deepFind(root, pred) {
      const stack = [root];
      while (stack.length) {
        const current = stack.shift();
        const kids = current.querySelectorAll ? Array.from(current.querySelectorAll("*")) : [];
        for (const node of kids) {
          if (pred(node)) return node;
          if (node.shadowRoot) stack.push(node.shadowRoot);
        }
      }
      return null;
    }

    function deepFindAll(root, pred) {
      const found = [];
      const stack = [root];
      while (stack.length) {
        const current = stack.shift();
        const kids = current.querySelectorAll ? Array.from(current.querySelectorAll("*")) : [];
        for (const node of kids) {
          if (pred(node)) found.push(node);
          if (node.shadowRoot) stack.push(node.shadowRoot);
        }
      }
      return found;
    }

    async function waitForPage() {
      const deadline = Date.now() + 15000;
      while (Date.now() < deadline) {
        const page = deepFind(document, (node) => node.tagName && node.tagName.toLowerCase() === "settings-search-engines-page");
        if (page && page.browserProxy_) return page;
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
      throw new Error("settings-search-engines-page not ready");
    }

    async function waitForDialog() {
      const deadline = Date.now() + 6000;
      while (Date.now() < deadline) {
        const dialog = deepFind(document, (node) => node.tagName && node.tagName.toLowerCase() === "settings-search-engine-edit-dialog");
        if (dialog) return dialog;
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      throw new Error("search engine edit dialog not ready");
    }

    function allEngines(list) {
      return [...(list.defaults || []), ...(list.actives || []), ...(list.others || [])];
    }

    function matches(engine) {
      return engine.keyword === KEYWORD ||
        engine.url === URL ||
        engine.url === OLD_URL ||
        engine.name === NAME ||
        engine.displayName === NAME ||
        engine.displayName === NAME + " (Default)" ||
        engine.shortName === NAME;
    }

    function allEngineEntries() {
      return deepFindAll(document, (node) => node.tagName && node.tagName.toLowerCase() === "settings-search-engine-entry");
    }

    async function makeDefault(engine) {
      const entry = allEngineEntries().find((candidate) => candidate.engine && candidate.engine.id === engine.id);
      if (!entry || typeof entry.onMakeDefaultClick_ !== "function") {
        throw new Error("configured search engine default action is not available");
      }
      entry.onMakeDefaultClick_();
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    const page = await waitForPage();
    const proxy = page.browserProxy_;
    let list = await proxy.getSearchEnginesList();
    let engine = allEngines(list).find(matches);
    let operation = "unchanged";

    if (engine) {
      if (engine.url !== URL || engine.keyword !== KEYWORD || engine.name !== NAME) {
        page.openEditDialog_(engine, page, false);
        const dialog = await waitForDialog();
        dialog.searchEngine_ = NAME;
        dialog.keyword_ = KEYWORD;
        dialog.queryUrl_ = URL;
        dialog.suggestionsUrl_ = "";
        dialog.updateActionButtonState_();
        await dialog.onActionButtonClick_();
        await new Promise((resolve) => setTimeout(resolve, 900));
        operation = "updated";
      }
    } else {
      const canAddPrimary = typeof page.onAddPrimarySearchEngineClick_ === "function";
      const button = deepFind(document, (node) => node.id === (canAddPrimary ? "addPrimarySearchEngine" : "addSearchEngine"));
      if (canAddPrimary) {
        page.onAddPrimarySearchEngineClick_({ target: button || page, preventDefault() {}, stopPropagation() {} });
      } else if (typeof page.onAddSearchEngineClick_ === "function") {
        page.onAddSearchEngineClick_({ target: button || page, preventDefault() {}, stopPropagation() {} });
      } else {
        throw new Error("no search-engine add method is available");
      }
      const dialog = await waitForDialog();
      dialog.searchEngine_ = NAME;
      dialog.keyword_ = KEYWORD;
      dialog.queryUrl_ = URL;
      dialog.suggestionsUrl_ = "";
      dialog.updateActionButtonState_();
      await dialog.onActionButtonClick_();
      await new Promise((resolve) => setTimeout(resolve, 1300));
      operation = "created";
    }

    list = await proxy.getSearchEnginesList();
    engine = allEngines(list).find(matches);
    if (!engine) throw new Error("configured search engine not found after save");

    await makeDefault(engine);

    list = await proxy.getSearchEnginesList();
    engine = allEngines(list).find(matches);
    if (!engine || !/\\(Default\\)/.test(engine.displayName || "")) {
      throw new Error("configured search engine was saved but did not become the default");
    }

    return {
      operation,
      id: engine.id,
      name: engine.name || engine.displayName,
      displayName: engine.displayName,
      keyword: engine.keyword,
      url: engine.url,
      canBeDefault: engine.canBeDefault,
      canBeRemoved: engine.canBeRemoved,
    };
  })()`;
}

(async () => {
  let browserProcess;
  try {
    browserProcess = spawn(exe, [
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${userDataDir}`,
      `--profile-directory=${profileDirectory}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-background-mode",
      "chrome://settings/searchEngines",
    ], { detached: false, stdio: "ignore", windowsHide: true });

    await waitForCdp();
    const targets = await fetchJson(`http://127.0.0.1:${port}/json/list`);
    const target = targets.find((candidate) => candidate.type === "page");
    if (!target) throw new Error("No page target found");

    const page = await cdp(target.webSocketDebuggerUrl);
    await page.send("Page.enable");
    await page.send("Runtime.enable");
    await page.send("Page.navigate", { url: "chrome://settings/searchEngines" });
    await sleep(1800);

    const result = await page.send("Runtime.evaluate", {
      expression: configureExpression(),
      awaitPromise: true,
      returnByValue: true,
    });
    page.close();

    if (result.result?.exceptionDetails) {
      throw new Error(JSON.stringify(result.result.exceptionDetails));
    }

    const version = await fetchJson(`http://127.0.0.1:${port}/json/version`);
    const browser = await cdp(version.webSocketDebuggerUrl);
    await browser.send("Browser.close");
    browser.close();

    console.log(JSON.stringify({ profileDirectory, result: result.result.result.value }));
    await sleep(1000);
  } catch (error) {
    console.error(JSON.stringify({ profileDirectory, error: error.message }));
    process.exitCode = 1;
  } finally {
    if (browserProcess && !browserProcess.killed) {
      browserProcess.kill();
    }
  }
})();
'@

    Set-Content -LiteralPath $configureScript -Value $configureHelper -Encoding UTF8

    Write-Host "Wrote local helper files to $helperDir"
}

function Register-LocalScheduledTasks {
    param([string]$NodePath)

    $startupAction = New-ScheduledTaskAction `
        -Execute "wscript.exe" `
        -Argument "`"$startupLauncher`""
    $startupTrigger = New-ScheduledTaskTrigger -AtLogOn
    $startupSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $startupSettings.ExecutionTimeLimit = "PT30M"
    $startupSettings.Hidden = $true

    Register-ScheduledTask `
        -TaskName $startupTaskName `
        -Action $startupAction `
        -Trigger $startupTrigger `
        -Settings $startupSettings `
        -Description "Start the AnonExplo SearXNG browser-search stack at user logon." `
        -Force | Out-Null

    $redirectorAction = New-ScheduledTaskAction `
        -Execute "wscript.exe" `
        -Argument "`"$redirectorLauncher`""
    $redirectorTrigger = New-ScheduledTaskTrigger -AtLogOn
    $redirectorSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $redirectorSettings.ExecutionTimeLimit = "PT0S"
    $redirectorSettings.Hidden = $true

    Register-ScheduledTask `
        -TaskName $redirectorTaskName `
        -Action $redirectorAction `
        -Trigger $redirectorTrigger `
        -Settings $redirectorSettings `
        -Description "Run the AnonExplo browser search fallback redirector." `
        -Force | Out-Null

    Write-Host "Registered scheduled tasks:"
    Write-Host "  - $startupTaskName"
    Write-Host "  - $redirectorTaskName"
}

function Repair-DockerDesktopRunEntry {
    if ($SkipDockerRunEntryRepair -or $NoDockerDesktopStart) {
        return
    }

    if (-not (Test-Path -LiteralPath $dockerDesktopLauncher)) {
        return
    }

    $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $currentValue = $null
    try {
        $currentValue = Get-ItemPropertyValue -Path $runKey -Name "Docker Desktop" -ErrorAction Stop
    } catch {
        return
    }

    if ($currentValue -and $currentValue -match "Docker Desktop\.exe") {
        $newValue = "wscript.exe `"$dockerDesktopLauncher`""
        Set-ItemProperty -Path $runKey -Name "Docker Desktop" -Value $newValue
        Write-Host "Updated the Docker Desktop logon entry to use a hidden CLI launcher."
    }
}

function Repair-ExistingScheduledTasks {
    $startupTask = Get-ScheduledTask -TaskName $startupTaskName -ErrorAction SilentlyContinue
    $redirectorTask = Get-ScheduledTask -TaskName $redirectorTaskName -ErrorAction SilentlyContinue
    $startupActionText = if ($startupTask) { ($startupTask.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " | " } else { "" }
    $redirectorActionText = if ($redirectorTask) { ($redirectorTask.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " | " } else { "" }

    if ($startupActionText -like "*$startupLauncher*" -and $redirectorActionText -like "*$redirectorLauncher*") {
        Write-Host "Existing scheduled tasks already use hidden launchers."
        return
    }

    $startupTaskRun = "wscript.exe `"$startupLauncher`""
    $redirectorTaskRun = "wscript.exe `"$redirectorLauncher`""

    & schtasks.exe /Change /TN $startupTaskName /TR $startupTaskRun /ENABLE | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not repair existing scheduled task '$startupTaskName'."
    }

    & schtasks.exe /Change /TN $redirectorTaskName /TR $redirectorTaskRun /ENABLE | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not repair existing scheduled task '$redirectorTaskName'."
    }

    Write-Host "Updated existing scheduled tasks to use hidden launchers."
}

function Register-StartupFolderLaunchers {
    param([string]$NodePath)

    $startupFolder = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
    if (-not $startupFolder) {
        throw "Could not resolve the current user's Startup folder."
    }

    $startupFolderStackLauncher = Join-Path $startupFolder "AnonExplo SearXNG Startup.vbs"
    $startupFolderRedirectorLauncher = Join-Path $startupFolder "AnonExplo Search Fallback Redirector.vbs"

    Copy-Item -LiteralPath $startupLauncher -Destination $startupFolderStackLauncher -Force
    Copy-Item -LiteralPath $redirectorLauncher -Destination $startupFolderRedirectorLauncher -Force

    Write-Host "Scheduled-task registration was not available, so Startup folder launchers were written:"
    Write-Host "  - $startupFolderStackLauncher"
    Write-Host "  - $startupFolderRedirectorLauncher"
}

function Stop-ManagedRedirectorIfRunning {
    $listeners = @(Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $RedirectorPort -State Listen -ErrorAction SilentlyContinue)
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if ($process -and $process.CommandLine -like "*search-fallback.js*") {
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
            continue
        }

        if ($process) {
            throw "Port $RedirectorPort is already used by PID $($listener.OwningProcess): $($process.CommandLine)"
        }
        throw "Port $RedirectorPort is already used by PID $($listener.OwningProcess)."
    }
}

function Read-ProfileNames {
    param([string]$UserDataDir)

    $names = @{}
    $localStatePath = Join-Path $UserDataDir "Local State"
    if (-not (Test-Path -LiteralPath $localStatePath)) {
        return $names
    }

    try {
        $state = Get-Content -LiteralPath $localStatePath -Raw | ConvertFrom-Json
        $infoCache = $state.profile.info_cache
        if (-not $infoCache) {
            return $names
        }

        foreach ($property in $infoCache.PSObject.Properties) {
            $label = @(
                $property.Value.name,
                $property.Value.shortcut_name,
                $property.Value.gaia_name,
                $property.Value.user_name
            ) | Where-Object { $_ } | Select-Object -First 1
            if ($label) {
                $names[$property.Name] = $label
            }
        }
    } catch {
        Write-Warning "Could not parse profile names from ${localStatePath}: $($_.Exception.Message)"
    }

    return $names
}

function Get-ChromiumProfiles {
    param([string]$UserDataDir)

    if (-not (Test-Path -LiteralPath $UserDataDir)) {
        return @()
    }

    $profileNames = Read-ProfileNames -UserDataDir $UserDataDir
    $profileDirs = @(Get-ChildItem -LiteralPath $UserDataDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "Default" -or $_.Name -like "Profile *" } |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "Preferences") } |
        Sort-Object Name)

    return @($profileDirs | ForEach-Object {
        [pscustomobject]@{
            Directory = $_.Name
            Path = $_.FullName
            DisplayName = if ($profileNames.ContainsKey($_.Name)) { $profileNames[$_.Name] } else { $_.Name }
        }
    })
}

function Get-ProcessesForExe {
    param([string]$ExePath)

    $resolved = (Resolve-Path -LiteralPath $ExePath).Path
    return @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -eq $resolved } catch { $false }
    })
}

function Stop-BrowserForAutomation {
    param(
        [string]$BrowserName,
        [string]$ExePath
    )

    $processes = Get-ProcessesForExe -ExePath $ExePath
    if (-not $processes) {
        return
    }

    if (-not $ForceCloseBrowsers) {
        throw "$BrowserName is running. Close it first or rerun with -ForceCloseBrowsers."
    }

    Write-Host "Closing running $BrowserName processes for profile configuration..."
    foreach ($process in $processes) {
        try {
            if ($process.MainWindowHandle -ne 0) {
                [void]$process.CloseMainWindow()
            }
        } catch {}
    }

    Start-Sleep -Seconds 3
    $remaining = Get-ProcessesForExe -ExePath $ExePath
    foreach ($process in $remaining) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

function Configure-ChromiumBrowser {
    param(
        [string]$BrowserName,
        [string]$ExePath,
        [string]$UserDataDir,
        [int]$StartingPort,
        [string]$NodePath
    )

    if (-not $ExePath) {
        Write-Warning "$BrowserName executable was not found; skipping."
        return 0
    }
    if (-not $UserDataDir) {
        Write-Warning "$BrowserName user-data directory was not found; skipping."
        return 0
    }

    Stop-BrowserForAutomation -BrowserName $BrowserName -ExePath $ExePath

    $profiles = @(Get-ChromiumProfiles -UserDataDir $UserDataDir)
    if (-not $profiles) {
        Write-Warning "No $BrowserName profiles were discovered under $UserDataDir."
        return 0
    }

    $configured = 0
    foreach ($profile in $profiles) {
        $port = $StartingPort + $configured
        Write-Host "Configuring $BrowserName profile '$($profile.DisplayName)' ($($profile.Directory)) on CDP port $port..."
        $output = & $NodePath $configureScript $ExePath $UserDataDir $profile.Directory $port $browserSearchUrl $searchName $searchKeyword 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "$BrowserName profile '$($profile.DisplayName)' failed: $($output -join "`n")"
        }
        Write-Host "  $($output -join "`n")"
        $configured += 1
    }

    return $configured
}

function Resolve-BraveTarget {
    $exe = Resolve-FirstExistingPath -Candidates @(
        $BraveExe,
        (Join-Path $env:ProgramFiles "BraveSoftware\Brave-Browser\Application\brave.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "BraveSoftware\Brave-Browser\Application\brave.exe"),
        (Join-Path $env:LOCALAPPDATA "BraveSoftware\Brave-Browser\Application\brave.exe")
    )
    $userData = Resolve-FirstExistingPath -Candidates @(
        $BraveUserDataDir,
        (Join-Path $env:LOCALAPPDATA "BraveSoftware\Brave-Browser\User Data"),
        (Join-Path $env:LOCALAPPDATA "BraveSoftware\Brave-Browser\User")
    )

    return [pscustomobject]@{ Name = "Brave"; Exe = $exe; UserDataDir = $userData }
}

function Resolve-HeliumTarget {
    $exe = Resolve-FirstExistingPath -Candidates @(
        $HeliumExe,
        (Join-Path $env:LOCALAPPDATA "imput\Helium\Application\chrome.exe"),
        (Join-Path $env:ProgramFiles "Helium\Application\chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Helium\Application\chrome.exe")
    )
    $userData = Resolve-FirstExistingPath -Candidates @(
        $HeliumUserDataDir,
        (Join-Path $env:LOCALAPPDATA "imput\Helium\User Data"),
        (Join-Path $env:LOCALAPPDATA "imput\Helium\User")
    )

    return [pscustomobject]@{ Name = "Helium"; Exe = $exe; UserDataDir = $userData }
}

$nodePath = Get-NodePath
Assert-NodeCapabilities -NodePath $nodePath -NeedsWebSocket:(-not $SkipBrowserConfiguration)
Write-LocalHelperFiles -NodePath $nodePath
Repair-DockerDesktopRunEntry

if (-not $SkipTaskRegistration) {
    try {
        Register-LocalScheduledTasks -NodePath $nodePath
        $startupLaunchMode = "ScheduledTask"
    } catch {
        $existingStartupTask = Get-ScheduledTask -TaskName $startupTaskName -ErrorAction SilentlyContinue
        $existingRedirectorTask = Get-ScheduledTask -TaskName $redirectorTaskName -ErrorAction SilentlyContinue
        if ($existingStartupTask -and $existingRedirectorTask) {
            Write-Warning "Could not overwrite existing scheduled tasks: $($_.Exception.Message)"
            Repair-ExistingScheduledTasks
            $startupLaunchMode = "ExistingScheduledTask"
        } elseif ($NoStartupFolderFallback) {
            throw
        } else {
            Write-Warning "Could not register scheduled tasks: $($_.Exception.Message)"
            Register-StartupFolderLaunchers -NodePath $nodePath
            $startupLaunchMode = "StartupFolder"
        }
    }
}

if (-not $NoStartNow) {
    if ($startupLaunchMode -eq "ScheduledTask" -or $startupLaunchMode -eq "ExistingScheduledTask") {
        Write-Host "Starting scheduled tasks now..."
        Start-ScheduledTask -TaskName $startupTaskName
        Stop-ManagedRedirectorIfRunning
        Start-ScheduledTask -TaskName $redirectorTaskName
    } elseif ($startupLaunchMode -eq "StartupFolder") {
        Write-Host "Starting local helpers now..."
        Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $startupScript) -WindowStyle Hidden
        Stop-ManagedRedirectorIfRunning
        Start-Process -FilePath $nodePath -ArgumentList @($redirectorScript) -WindowStyle Hidden
    } else {
        Write-Warning "Skipping immediate startup because no startup registration mode was selected."
    }
}

if (-not $SkipBrowserConfiguration) {
    $totalProfiles = 0
    $nextPort = $CdpPortBase

    if (-not $SkipBrave) {
        $target = Resolve-BraveTarget
        $count = Configure-ChromiumBrowser -BrowserName $target.Name -ExePath $target.Exe -UserDataDir $target.UserDataDir -StartingPort $nextPort -NodePath $nodePath
        $totalProfiles += $count
        $nextPort += [Math]::Max($count, 1) + 10
    }

    if (-not $SkipHelium) {
        $target = Resolve-HeliumTarget
        $count = Configure-ChromiumBrowser -BrowserName $target.Name -ExePath $target.Exe -UserDataDir $target.UserDataDir -StartingPort $nextPort -NodePath $nodePath
        $totalProfiles += $count
    }

    Write-Host "Configured $totalProfiles browser profile(s)."
} else {
    Write-Host "Skipped browser profile configuration."
}

Write-Host "Browser search setup complete."
Write-Host "Browser search URL: $browserSearchUrl"
Write-Host "Verify with: curl.exe -s -I `"http://127.0.0.1:$RedirectorPort/search?q=anonexplo-check`""

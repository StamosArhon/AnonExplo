param(
    [switch]$RequireModelRuntime
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

function Get-EnvValue {
    param(
        [string]$Key,
        [string]$DefaultValue = ""
    )

    foreach ($path in @((Join-Path $root ".env"), (Join-Path $root ".env.example"))) {
        if (-not (Test-Path $path)) {
            continue
        }

        $match = Get-Content -LiteralPath $path | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))=(.*)$" } | Select-Object -First 1
        if ($match) {
            $value = ($match -replace "^\s*$([regex]::Escape($Key))=", "").Trim()
            if ($value -and -not $value.StartsWith("replace-with-")) {
                return $value
            }
        }
    }

    return $DefaultValue
}

function Get-ServiceContainerId {
    param([string]$ServiceName)

    $containerId = docker compose ps -q $ServiceName 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    return $containerId.Trim()
}

function Wait-ForServiceStatus {
    param(
        [string]$ServiceName,
        [string]$ExpectedStatus,
        [int]$Attempts = 15
    )

    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        $containerId = Get-ServiceContainerId -ServiceName $ServiceName
        if ($containerId) {
            $status = docker inspect $containerId --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" 2>$null
            if ($LASTEXITCODE -eq 0 -and $status.Trim() -eq $ExpectedStatus) {
                return $true
            }
        }

        Start-Sleep -Seconds 2
    }

    return $false
}

function Get-ServicePortBindings {
    param([string]$ServiceName)

    $containerId = Get-ServiceContainerId -ServiceName $ServiceName
    if (-not $containerId) {
        throw "Could not find a running container for service '$ServiceName'."
    }

    return docker inspect $containerId --format "{{json .HostConfig.PortBindings}}"
}

function Invoke-BackendPython {
    param([string]$Script)

    $Script | docker compose exec -T backend python -
    if ($LASTEXITCODE -ne 0) {
        throw "Backend-side validation probe failed."
    }
}

try {
    Write-Host "Validating docker compose configuration..."
    docker compose config | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker compose config failed." }

    Write-Host "Validating llama.cpp profile configuration..."
    docker compose --profile llamacpp config | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "llama.cpp profile config failed." }

    Write-Host "Building repo-managed images..."
    docker compose build ui backend fetcher
    if ($LASTEXITCODE -ne 0) { throw "docker compose build failed." }

    Write-Host "Running backend tests..."
    docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }

    Write-Host "Running fetcher tests..."
    docker compose run --rm --no-deps fetcher python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Fetcher tests failed." }

    Write-Host "Running base stack smoke test..."
    docker compose up -d ui backend fetcher search-provider
    if ($LASTEXITCODE -ne 0) { throw "Base stack failed to start." }

    if (-not (Wait-ForServiceStatus -ServiceName "backend" -ExpectedStatus "healthy")) {
        docker compose logs backend fetcher search-provider ui
        throw "Backend health check failed."
    }

    if (-not (Wait-ForServiceStatus -ServiceName "fetcher" -ExpectedStatus "healthy")) {
        docker compose logs fetcher
        throw "Fetcher health check failed."
    }

    if (-not (Wait-ForServiceStatus -ServiceName "ui" -ExpectedStatus "healthy")) {
        docker compose logs ui
        throw "UI smoke check failed."
    }

    if (-not (Wait-ForServiceStatus -ServiceName "search-provider" -ExpectedStatus "running")) {
        docker compose logs search-provider
        throw "Search provider failed to stay running."
    }

    $backendPorts = Get-ServicePortBindings -ServiceName "backend"
    if ($backendPorts -notmatch '"8000/tcp"' -or $backendPorts -notmatch '"HostIp":"127.0.0.1"') {
        throw "Backend localhost port binding is missing."
    }

    $uiPorts = Get-ServicePortBindings -ServiceName "ui"
    if ($uiPorts -notmatch '"8080/tcp"' -or $uiPorts -notmatch '"HostPort":"3000"') {
        throw "UI localhost port binding is missing."
    }

    $modelFileName = Get-EnvValue -Key "MODEL_FILE_NAME" -DefaultValue "Qwen2.5-7B-Instruct.Q4_K_M.gguf"
    $expectedModelSha = (Get-EnvValue -Key "MODEL_FILE_SHA256").ToLowerInvariant()
    $modelFilePath = Join-Path $root "data\models\$modelFileName"
    $configuredModelName = Get-EnvValue -Key "MODEL_NAME" -DefaultValue "qwen2.5-7b-instruct-q4_k_m"

    if (-not (Test-Path -LiteralPath $modelFilePath)) {
        $skipMessage = "Skipping model runtime smoke test because '$modelFileName' was not found in data\models."
        if ($RequireModelRuntime) {
            throw $skipMessage
        }

        Write-Warning $skipMessage
        Write-Host "Validation completed successfully without the optional model runtime probe."
        return
    }

    if ($expectedModelSha) {
        Write-Host "Verifying configured model checksum..."
        $actualModelSha = (Get-FileHash -LiteralPath $modelFilePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualModelSha -ne $expectedModelSha) {
            throw "Configured model checksum does not match MODEL_FILE_SHA256."
        }
    }

    $env:MODEL_NAME = $configuredModelName
    $env:MODEL_FILE_NAME = $modelFileName

    Write-Host "Running model runtime smoke test..."
    docker compose --profile llamacpp up -d model-backend backend
    if ($LASTEXITCODE -ne 0) { throw "Model runtime services failed to start." }

    if (-not (Wait-ForServiceStatus -ServiceName "model-backend" -ExpectedStatus "healthy" -Attempts 240)) {
        docker compose logs model-backend backend
        throw "Model runtime health check failed."
    }

    Invoke-BackendPython -Script @"
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/model/runtime", timeout=20) as response:
    payload = json.load(response)

if not payload.get("ready"):
    raise SystemExit(f"Model runtime not ready: {payload.get('status')} / {payload.get('error')}")

if payload.get("configured_model") != "$configuredModelName":
    raise SystemExit("Configured model name reported by the backend did not match the expected model.")
"@

    Invoke-BackendPython -Script @"
import json
import urllib.request

payload = {
    "model": "$configuredModelName",
    "messages": [{"role": "user", "content": "Reply with the single word READY."}],
    "temperature": 0.0,
    "max_tokens": 8,
}
request = urllib.request.Request(
    "http://model-backend:8080/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=120) as response:
    data = json.load(response)

answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
if not isinstance(answer, str) or not answer.strip():
    raise SystemExit("Model runtime returned an empty chat response.")
"@

    Write-Host "Validation completed successfully, including the local model runtime probe."
} finally {
    Remove-Item Env:MODEL_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:MODEL_FILE_NAME -ErrorAction SilentlyContinue
    docker compose --profile llamacpp down --remove-orphans | Out-Null
    Pop-Location
}

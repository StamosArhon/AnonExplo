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

function Get-NamedValue {
    param(
        [object]$Container,
        [string]$Name,
        [string]$Kind
    )

    $property = $Container.PSObject.Properties | Where-Object Name -eq $Name | Select-Object -First 1
    if (-not $property) {
        throw "Missing $Kind '$Name' in the compose configuration."
    }

    return $property.Value
}

function Get-NamedKeys {
    param([object]$Container)

    if ($null -eq $Container) {
        return @()
    }

    return @($Container.PSObject.Properties | ForEach-Object { $_.Name })
}

function Assert-SetEquality {
    param(
        [string]$Label,
        [string[]]$Actual,
        [string[]]$Expected
    )

    $normalizedActual = @($Actual | Sort-Object -Unique)
    $normalizedExpected = @($Expected | Sort-Object -Unique)

    if (($normalizedActual -join ",") -ne ($normalizedExpected -join ",")) {
        throw "$Label did not match. Expected '$($normalizedExpected -join ", ")' but found '$($normalizedActual -join ", ")'."
    }
}

function Get-ComposeConfig {
    param([switch]$UseLlamaCppProfile)

    if ($UseLlamaCppProfile) {
        $json = docker compose --profile llamacpp config --format json
    } else {
        $json = docker compose config --format json
    }

    if ($LASTEXITCODE -ne 0) {
        throw "docker compose config failed."
    }

    return $json | ConvertFrom-Json
}

function Test-DigestPinnedImage {
    param([string]$ImageReference)

    return $ImageReference -match "@sha256:[0-9a-f]{64}$"
}

function Assert-LocalOnlyCorsOrigins {
    param([string]$Origins)

    foreach ($origin in ($Origins -split "," | Where-Object { $_.Trim() })) {
        $uri = $null
        if (-not [Uri]::TryCreate($origin.Trim(), [UriKind]::Absolute, [ref]$uri)) {
            throw "CORS origin '$origin' is not a valid absolute URI."
        }

        if ($uri.Host -notin @("127.0.0.1", "localhost")) {
            throw "CORS origin '$origin' is not localhost-only."
        }
    }
}

function Assert-ServiceHasHealthcheck {
    param(
        [object]$ComposeConfig,
        [string]$ServiceName
    )

    $service = Get-NamedValue -Container $ComposeConfig.services -Name $ServiceName -Kind "service"
    $hasHealthcheck = $service.PSObject.Properties | Where-Object Name -eq "healthcheck" | Select-Object -First 1
    if (-not $hasHealthcheck) {
        throw "Service '$ServiceName' is missing a healthcheck."
    }
}

function Assert-ServiceSecurityDefaults {
    param(
        [object]$ComposeConfig,
        [string]$ServiceName
    )

    $service = Get-NamedValue -Container $ComposeConfig.services -Name $ServiceName -Kind "service"

    if (-not $service.read_only) {
        throw "Service '$ServiceName' must be read-only by default."
    }

    if ($service.cap_drop -notcontains "ALL") {
        throw "Service '$ServiceName' must drop all Linux capabilities by default."
    }

    if ($service.security_opt -notcontains "no-new-privileges:true") {
        throw "Service '$ServiceName' must enable no-new-privileges."
    }
}

function Assert-ComposeHardeningPolicy {
    param(
        [object]$BaseComposeConfig,
        [object]$LlamaComposeConfig,
        [string]$UiPort,
        [string]$BackendPort,
        [string]$SearxngUiPort
    )

    $coreInternal = Get-NamedValue -Container $BaseComposeConfig.networks -Name "core_internal" -Kind "network"
    if (-not $coreInternal.internal) {
        throw "The core_internal network must remain internal."
    }

    $modelInternal = Get-NamedValue -Container $LlamaComposeConfig.networks -Name "model_internal" -Kind "network"
    if (-not $modelInternal.internal) {
        throw "The model_internal network must remain internal."
    }

    $servicesWithPorts = @(
        $BaseComposeConfig.services.PSObject.Properties |
            Where-Object {
                ($_.Value.PSObject.Properties | Where-Object Name -eq "ports" | Select-Object -First 1) -and $_.Value.ports
            } |
            ForEach-Object { $_.Name }
    )
    Assert-SetEquality -Label "Services with published ports" -Actual $servicesWithPorts -Expected @("host-gateway")

    $hostGateway = Get-NamedValue -Container $BaseComposeConfig.services -Name "host-gateway" -Kind "service"
    $expectedPublishedPorts = @{
        3000 = $UiPort
        8000 = $BackendPort
        8085 = $SearxngUiPort
    }

    if (@($hostGateway.ports).Count -ne $expectedPublishedPorts.Count) {
        throw "The host-gateway service published an unexpected number of ports."
    }

    foreach ($targetPort in $expectedPublishedPorts.Keys) {
        $portBinding = @($hostGateway.ports | Where-Object { $_.target -eq [int]$targetPort }) | Select-Object -First 1
        if (-not $portBinding) {
            throw "The host-gateway service is missing the published port for target $targetPort."
        }

        if ($portBinding.host_ip -ne "127.0.0.1") {
            throw "Published port $targetPort must bind to 127.0.0.1."
        }

        if ($portBinding.published -ne [string]$expectedPublishedPorts[$targetPort]) {
            throw "Published port $targetPort did not match the expected host port $($expectedPublishedPorts[$targetPort])."
        }
    }

    $expectedNetworks = @{
        "host-gateway"   = @("core_internal", "host_access")
        "ui"             = @("core_internal")
        "backend"        = @("core_internal", "model_internal")
        "fetcher"        = @("core_internal", "egress")
        "search-provider" = @("core_internal", "egress")
    }

    foreach ($serviceName in $expectedNetworks.Keys) {
        $service = Get-NamedValue -Container $BaseComposeConfig.services -Name $serviceName -Kind "service"
        Assert-SetEquality -Label "Service '$serviceName' networks" -Actual (Get-NamedKeys -Container $service.networks) -Expected $expectedNetworks[$serviceName]
        Assert-ServiceSecurityDefaults -ComposeConfig $BaseComposeConfig -ServiceName $serviceName
        Assert-ServiceHasHealthcheck -ComposeConfig $BaseComposeConfig -ServiceName $serviceName
    }

    $modelBackend = Get-NamedValue -Container $LlamaComposeConfig.services -Name "model-backend" -Kind "service"
    Assert-SetEquality -Label "Service 'model-backend' networks" -Actual (Get-NamedKeys -Container $modelBackend.networks) -Expected @("model_internal")
    Assert-ServiceSecurityDefaults -ComposeConfig $LlamaComposeConfig -ServiceName "model-backend"
    Assert-ServiceHasHealthcheck -ComposeConfig $LlamaComposeConfig -ServiceName "model-backend"

    foreach ($serviceName in @("host-gateway", "search-provider")) {
        $service = Get-NamedValue -Container $BaseComposeConfig.services -Name $serviceName -Kind "service"
        if (-not (Test-DigestPinnedImage -ImageReference $service.image)) {
            throw "Service '$serviceName' must use a digest-pinned image reference."
        }
    }

    if (-not (Test-DigestPinnedImage -ImageReference $modelBackend.image)) {
        throw "Service 'model-backend' must use a digest-pinned image reference."
    }

    $backend = Get-NamedValue -Container $BaseComposeConfig.services -Name "backend" -Kind "service"
    Assert-LocalOnlyCorsOrigins -Origins $backend.environment.CORS_ALLOWED_ORIGINS
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

function Test-HostHttpEndpoint {
    param(
        [string]$Url,
        [int]$Attempts = 15
    )

    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return $true
            }
        } catch {
        }

        Start-Sleep -Seconds 2
    }

    return $false
}

function Invoke-BackendPython {
    param([string]$Script)

    $Script | docker compose exec -T backend python -
    if ($LASTEXITCODE -ne 0) {
        throw "Backend-side validation probe failed."
    }
}

try {
    $uiPort = Get-EnvValue -Key "UI_PORT" -DefaultValue "3000"
    $backendPort = Get-EnvValue -Key "BACKEND_PORT" -DefaultValue "8000"
    $searxngUiPort = Get-EnvValue -Key "SEARXNG_UI_PORT" -DefaultValue "8085"

    Write-Host "Validating docker compose configuration..."
    $composeConfig = Get-ComposeConfig

    Write-Host "Validating llama.cpp profile configuration..."
    $llamaComposeConfig = Get-ComposeConfig -UseLlamaCppProfile

    Write-Host "Checking compose hardening policy..."
    Assert-ComposeHardeningPolicy `
        -BaseComposeConfig $composeConfig `
        -LlamaComposeConfig $llamaComposeConfig `
        -UiPort $uiPort `
        -BackendPort $backendPort `
        -SearxngUiPort $searxngUiPort

    Write-Host "Building repo-managed images..."
    docker compose build ui backend fetcher
    if ($LASTEXITCODE -ne 0) { throw "docker compose build failed." }

    Write-Host "Running backend tests..."
    docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }

    Write-Host "Running fetcher tests..."
    docker compose run --rm --no-deps fetcher python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Fetcher tests failed." }

    Write-Host "Running UI server syntax check..."
    python -m py_compile apps/ui/server.py
    if ($LASTEXITCODE -ne 0) { throw "UI server syntax validation failed." }

    Write-Host "Running UI client syntax check..."
    node --check apps/ui/static/app.js
    if ($LASTEXITCODE -ne 0) { throw "UI client syntax validation failed." }

    Write-Host "Running base stack smoke test..."
    docker compose up -d host-gateway ui backend fetcher search-provider
    if ($LASTEXITCODE -ne 0) { throw "Base stack failed to start." }

    if (-not (Wait-ForServiceStatus -ServiceName "backend" -ExpectedStatus "healthy")) {
        docker compose logs host-gateway backend fetcher search-provider ui
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

    if (-not (Wait-ForServiceStatus -ServiceName "search-provider" -ExpectedStatus "healthy")) {
        docker compose logs search-provider
        throw "Search provider health check failed."
    }

    if (-not (Wait-ForServiceStatus -ServiceName "host-gateway" -ExpectedStatus "healthy")) {
        docker compose logs host-gateway ui backend search-provider
        throw "Host gateway health check failed."
    }

    $gatewayPorts = Get-ServicePortBindings -ServiceName "host-gateway"
    foreach ($targetPort in @("3000", "8000", "8085")) {
        if ($gatewayPorts -notmatch ('"' + $targetPort + '/tcp"')) {
            throw "The host gateway is missing port binding metadata for $targetPort/tcp."
        }
    }

    if ($gatewayPorts -notmatch ('"HostPort":"' + $uiPort + '"') -or $gatewayPorts -notmatch '"HostIp":"127.0.0.1"') {
        throw "UI localhost port binding is missing or not bound to 127.0.0.1."
    }

    if ($gatewayPorts -notmatch ('"HostPort":"' + $backendPort + '"') -or $gatewayPorts -notmatch '"HostIp":"127.0.0.1"') {
        throw "Backend localhost port binding is missing or not bound to 127.0.0.1."
    }

    if ($gatewayPorts -notmatch ('"HostPort":"' + $searxngUiPort + '"') -or $gatewayPorts -notmatch '"HostIp":"127.0.0.1"') {
        throw "SearXNG localhost port binding is missing or not bound to 127.0.0.1."
    }

    if (-not (Test-HostHttpEndpoint -Url "http://127.0.0.1:$uiPort/")) {
        docker compose logs host-gateway ui
        throw "UI was not reachable on the Windows host at http://127.0.0.1:$uiPort/."
    }

    if (-not (Test-HostHttpEndpoint -Url "http://127.0.0.1:$backendPort/api/v1/health")) {
        docker compose logs host-gateway backend
        throw "Backend was not reachable on the Windows host at http://127.0.0.1:$backendPort/api/v1/health."
    }

    if (-not (Test-HostHttpEndpoint -Url "http://127.0.0.1:$searxngUiPort/")) {
        docker compose logs host-gateway search-provider
        throw "SearXNG was not reachable on the Windows host at http://127.0.0.1:$searxngUiPort/."
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

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

function Wait-ForContainerStatus {
    param(
        [string]$ContainerName,
        [string]$ExpectedStatus,
        [int]$Attempts = 15
    )

    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        $status = docker inspect $ContainerName --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" 2>$null
        if ($LASTEXITCODE -eq 0 -and $status.Trim() -eq $ExpectedStatus) {
            return $true
        }

        Start-Sleep -Seconds 2
    }

    return $false
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

    if (-not (Wait-ForContainerStatus -ContainerName "anonexplo-backend-1" -ExpectedStatus "healthy")) {
        docker compose logs backend fetcher search-provider ui
        throw "Backend health check failed."
    }

    if (-not (Wait-ForContainerStatus -ContainerName "anonexplo-fetcher-1" -ExpectedStatus "healthy")) {
        docker compose logs fetcher
        throw "Fetcher health check failed."
    }

    if (-not (Wait-ForContainerStatus -ContainerName "anonexplo-ui-1" -ExpectedStatus "healthy")) {
        docker compose logs ui
        throw "UI smoke check failed."
    }

    if (-not (Wait-ForContainerStatus -ContainerName "anonexplo-search-provider-1" -ExpectedStatus "running")) {
        docker compose logs search-provider
        throw "Search provider failed to stay running."
    }

    $backendPorts = docker inspect anonexplo-backend-1 --format "{{json .HostConfig.PortBindings}}"
    if ($backendPorts -notmatch '"8000/tcp"' -or $backendPorts -notmatch '"HostIp":"127.0.0.1"') {
        throw "Backend localhost port binding is missing."
    }

    $uiPorts = docker inspect anonexplo-ui-1 --format "{{json .HostConfig.PortBindings}}"
    if ($uiPorts -notmatch '"8080/tcp"' -or $uiPorts -notmatch '"HostPort":"3000"') {
        throw "UI localhost port binding is missing."
    }

    Write-Host "Validation completed successfully."
} finally {
    docker compose down --remove-orphans | Out-Null
    Pop-Location
}

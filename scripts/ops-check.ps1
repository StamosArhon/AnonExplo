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
            if ($value) {
                return $value
            }
        }
    }

    return $DefaultValue
}

function Invoke-OptionalJsonRequest {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 8
        return @{
            Reachable = $true
            StatusCode = $response.StatusCode
            Body = $response.Content | ConvertFrom-Json
        }
    } catch {
        return @{
            Reachable = $false
            StatusCode = $null
            Body = $null
            Error = $_.Exception.Message
        }
    }
}

function Test-OptionalEndpoint {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 8
        return @{
            Reachable = $true
            StatusCode = $response.StatusCode
        }
    } catch {
        return @{
            Reachable = $false
            StatusCode = $null
            Error = $_.Exception.Message
        }
    }
}

try {
    $uiPort = Get-EnvValue -Key "UI_PORT" -DefaultValue "3000"
    $backendPort = Get-EnvValue -Key "BACKEND_PORT" -DefaultValue "8000"
    $searxngUiPort = Get-EnvValue -Key "SEARXNG_UI_PORT" -DefaultValue "8085"

    $ui = Test-OptionalEndpoint -Url "http://127.0.0.1:$uiPort/"
    $backend = Invoke-OptionalJsonRequest -Url "http://127.0.0.1:$backendPort/api/v1/health"
    $searchUi = Test-OptionalEndpoint -Url "http://127.0.0.1:$searxngUiPort/"
    $runtime = Invoke-OptionalJsonRequest -Url "http://127.0.0.1:$backendPort/api/v1/model/runtime"

    Write-Host "AnonExplo Ops Check"
    Write-Host "-------------------"
    Write-Host ("UI            : " + ($(if ($ui.Reachable) { "ok (HTTP $($ui.StatusCode))" } else { "down - $($ui.Error)" })))
    Write-Host ("Backend       : " + ($(if ($backend.Reachable) { "$($backend.Body.status)" } else { "down - $($backend.Error)" })))
    Write-Host ("SearXNG UI    : " + ($(if ($searchUi.Reachable) { "ok (HTTP $($searchUi.StatusCode))" } else { "down - $($searchUi.Error)" })))

    if ($runtime.Reachable) {
        Write-Host ("Model runtime : " + $runtime.Body.status)
        if ($runtime.Body.error) {
            Write-Host ("Runtime note  : " + $runtime.Body.error)
        }
    } else {
        Write-Host ("Model runtime : down - " + $runtime.Error)
    }

    Write-Host ""
    Write-Host "docker compose ps"
    docker compose ps

    $failed = $false
    if (-not $ui.Reachable -or -not $backend.Reachable -or -not $searchUi.Reachable) {
        $failed = $true
    }

    if ($RequireModelRuntime -and ((-not $runtime.Reachable) -or (-not $runtime.Body.ready))) {
        $failed = $true
    }

    if ($failed) {
        Write-Host ""
        Write-Host "Suggested next steps:"
        Write-Host "  1. docker compose ps"
        Write-Host "  2. docker compose logs --tail=80 host-gateway backend fetcher search-provider model-backend"
        Write-Host "  3. powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime"
        exit 1
    }
} finally {
    Pop-Location
}

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    $compose = @('-f','docker-compose.yml','-f','docker-compose.proton-search.yml','--profile','proton-search')
    $raw = & docker compose @compose config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Compose config failed.' }
    $config = $raw | ConvertFrom-Json
    $port = [string]$config.services.'host-gateway'.ports[0].published
    . (Join-Path $PSScriptRoot 'compose-policy.ps1')
    Assert-SearchComposePolicy $config $port -Vpn
    $running = @(& docker compose @compose ps --format json | ForEach-Object { $_ | ConvertFrom-Json })
    Assert-SetEquality 'Running services' @($running | ForEach-Object Service) @('host-gateway','search-provider','search-vpn')
    if (@($running | Where-Object { $_.State -ne 'running' -or $_.Health -ne 'healthy' }).Count) {
        throw 'One or more search services are unhealthy.'
    }
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/" -TimeoutSec 15
    if ($response.Headers['Cache-Control'] -ne 'no-store' -or $response.Headers['Referrer-Policy'] -ne 'no-referrer') {
        throw 'Search privacy headers missing.'
    }
    & (Join-Path $PSScriptRoot 'check-proton-search.ps1')
    Write-Host "PASS: three healthy services; SearXNG at http://127.0.0.1:$port. No LLM required."
    Write-Host 'Local health is not upstream search quality; run test-browser-search.ps1 manually when needed.'
} finally { Pop-Location }

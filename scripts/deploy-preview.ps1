# Run only after validate.ps1 and test-preview.ps1 have passed for this checkout.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
function Read-QuietState {
    $errors = Invoke-RestMethod -Uri 'http://127.0.0.1:8085/stats/errors' -TimeoutSec 10
    foreach ($engine in $errors.PSObject.Properties) {
        foreach ($entry in $engine.Value) {
            if ($entry.exception_classname -match 'Captcha|Cloudflare') { throw 'Long-ban history needs review before restarting search.' }
        }
    }
    $stats = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8085/stats' -TimeoutSec 10
    return ($errors | ConvertTo-Json -Depth 15 -Compress) + $stats.Content
}
try {
    & (Join-Path $PSScriptRoot 'ops-check.ps1')
    $vpnBefore = docker inspect anonexplo-search-vpn-1 --format '{{.Id}}'
    Write-Host 'Checking a 180-second quiet/cooldown window before planned deployment; no searches.'
    Start-Sleep -Seconds 10
    $before = Read-QuietState
    foreach ($i in 1..6) { Start-Sleep -Seconds 30; Write-Host "Quiet window $($i*30)/180s" }
    if ((Read-QuietState) -ne $before) { throw 'Search activity changed; not restarting or automatically repeating.' }
    docker image tag anonexplo/searxng:date-merge-v1 anonexplo/searxng:before-preference-preview
    if ($LASTEXITCODE) { throw 'Cannot preserve rollback image.' }
    docker compose -f docker-compose.yml build search-provider
    if ($LASTEXITCODE) { throw 'Production build failed.' }
    . (Join-Path $PSScriptRoot 'image-identity.ps1')
    $candidate = docker image inspect --platform linux/amd64 anonexplo/searxng:validation --format '{{json .Descriptor}}' | ConvertFrom-Json
    $built = docker image inspect --platform linux/amd64 anonexplo/searxng:date-merge-v1 --format '{{json .Descriptor}}' | ConvertFrom-Json
    Assert-SameRuntimeManifest $candidate $built
    docker compose -f docker-compose.yml -f docker-compose.proton-search.yml --profile proton-search up -d --no-deps --wait --wait-timeout 120 search-provider host-gateway
    if ($LASTEXITCODE) { throw 'Search/gateway deployment failed; inspect before rollback.' }
    if ((docker inspect anonexplo-search-vpn-1 --format '{{.Id}}') -ne $vpnBefore) { throw 'VPN identity changed unexpectedly.' }
    & (Join-Path $PSScriptRoot 'start-preview.ps1')
    & (Join-Path $PSScriptRoot 'ops-check.ps1')
    Write-Host 'Opt-in preview deployed; VPN container unchanged; native search remains default.'
} finally { Pop-Location }

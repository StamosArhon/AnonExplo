$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    # Only the separate model restarts. Do not touch search/VPN/cooldowns.
    $coreNames = @('anonexplo-host-gateway-1','anonexplo-search-provider-1','anonexplo-search-vpn-1')
    $before = @{}
    foreach ($name in $coreNames) {
        $value = docker inspect $name --format '{{.Id}} {{.State.Health.Status}}'
        if ($LASTEXITCODE -or $value -notmatch ' healthy$') { throw 'Core health prerequisite failed.' }
        $before[$name] = $value
    }
    docker exec anonexplo-host-gateway-1 nginx -t
    if ($LASTEXITCODE) { throw 'Gateway configuration invalid; no service changed.' }
    . (Join-Path $PSScriptRoot 'preview-policy.ps1')
    $raw = docker compose -f docker-compose.preview.yml config --format json
    if ($LASTEXITCODE) { throw 'Preview configuration unavailable.' }
    Assert-PreviewPolicy ($raw | ConvertFrom-Json)
    docker compose -f docker-compose.preview.yml up -d --no-deps --force-recreate --wait --wait-timeout 180 reranker
    if ($LASTEXITCODE) { throw 'Local model update failed. Native search remains available.' }
    docker exec anonexplo-host-gateway-1 nginx -s reload
    if ($LASTEXITCODE) { throw 'Gateway reload failed. Check the existing native endpoint.' }
    foreach ($name in $coreNames) {
        $value = docker inspect $name --format '{{.Id}} {{.State.Health.Status}}'
        if ($LASTEXITCODE -or $value -ne $before[$name]) { throw 'Unexpected core replacement or health change.' }
    }
    python (Join-Path $PSScriptRoot 'check-preview-v2.py')
    if ($LASTEXITCODE) { throw 'Updated gateway verification failed.' }
    Write-Host 'Preferred coverage updated; gateway/search/VPN identities unchanged. No provider queries sent by deployment.'
} finally { Pop-Location }

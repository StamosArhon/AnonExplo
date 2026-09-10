$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
$saved = @{}
foreach ($key in @('COMPOSE_FILE','COMPOSE_PROFILES','COMPOSE_PROJECT_NAME','SEARXNG_UI_PORT')) {
    $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}
$env:COMPOSE_FILE = (Join-Path $root 'docker-compose.yml') + ';' + (Join-Path $root 'docker-compose.validation.yml')
$env:COMPOSE_PROFILES = ''
$env:COMPOSE_PROJECT_NAME = 'anonexplo-validation'
$env:SEARXNG_UI_PORT = '18085'
. (Join-Path $PSScriptRoot 'compose-policy.ps1')

function Assert-HttpPrivacy([string]$Path) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:18085$Path" -TimeoutSec 15
    if ($response.StatusCode -ne 200 -or $response.Headers['Cache-Control'] -ne 'no-store' -or
        $response.Headers['Referrer-Policy'] -ne 'no-referrer') { throw 'Search privacy headers or HTTP health failed.' }
}
try {
    Write-Host 'Validating isolated base and VPN Compose policies...'
    $raw = docker compose config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Base Compose config failed.' }
    $base = $raw | ConvertFrom-Json
    $raw = docker compose -f docker-compose.yml -f docker-compose.proton-search.yml --profile proton-search config --format json
    if ($LASTEXITCODE -ne 0) { throw 'VPN Compose config failed.' }
    $vpn = $raw | ConvertFrom-Json
    Assert-SearchComposePolicy $base '18085' -Validation
    Assert-SearchComposePolicy $vpn '18085' -Vpn
    & (Join-Path $PSScriptRoot 'test-compose-policy.ps1') -Base $base -Vpn $vpn
    $diskCache = @($base.services.'search-provider'.volumes | Where-Object target -eq '/var/cache/searxng')
    if ($diskCache.Count) { throw 'Validation must not mount the live cache.' }
    foreach ($script in Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1') {
        $errors = $null; $tokens = $null
        [System.Management.Automation.Language.Parser]::ParseFile($script.FullName, [ref]$tokens, [ref]$errors) | Out-Null
        if ($errors.Count) { throw "PowerShell syntax error: $($script.Name)" }
    }
    python -m unittest discover -s scripts/tests -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed.' }
    & (Join-Path $PSScriptRoot 'test-news-candidate.ps1')
    & (Join-Path $PSScriptRoot 'test-startup-helpers.ps1')
    & (Join-Path $PSScriptRoot 'test-image-identity.ps1')
    $productionImageBefore = @(docker image ls --no-trunc --quiet --filter 'reference=anonexplo/searxng:date-merge-v1') -join ','
    if ($LASTEXITCODE -ne 0) { throw 'Cannot snapshot production image tag.' }
    # Build the guarded repair from its pinned base; RUN steps have no network.
    docker compose build
    if ($LASTEXITCODE -ne 0) { throw 'Compose build failed.' }
    $productionImageAfter = @(docker image ls --no-trunc --quiet --filter 'reference=anonexplo/searxng:date-merge-v1') -join ','
    if ($LASTEXITCODE -ne 0 -or $productionImageBefore -ne $productionImageAfter) { throw 'Validation changed the production image tag.' }
    Write-Host 'Built isolated validation image; production image tag unchanged.'
    & (Join-Path $PSScriptRoot 'test-ddg-diagnostic.ps1') -Image 'anonexplo/searxng:validation'
    & (Join-Path $PSScriptRoot 'test-ddg-diagnostic.ps1') -Transport -Image 'anonexplo/searxng:validation'
    & (Join-Path $PSScriptRoot 'test-ddg-diagnostic.ps1') -TimeoutSemantics -Image 'anonexplo/searxng:validation'
    docker compose up -d --wait --wait-timeout 120 host-gateway search-provider
    if ($LASTEXITCODE -ne 0) { throw 'Isolated search stack failed to start.' }
    foreach ($path in @('/','/preferences','/config','/stats')) { Assert-HttpPrivacy $path }
    $id = docker compose ps -q host-gateway
    $ports = docker inspect $id --format '{{json .HostConfig.PortBindings}}' | ConvertFrom-Json
    if (@($ports.PSObject.Properties).Count -ne 1 -or $ports.'8085/tcp'[0].HostPort -ne '18085' -or
        $ports.'8085/tcp'[0].HostIp -ne '127.0.0.1') { throw 'Runtime publication mismatch.' }
    Get-Content -Raw (Join-Path $PSScriptRoot 'check-search-settings.py') | docker compose exec -T search-provider /usr/local/searxng/.venv/bin/python -
    if ($LASTEXITCODE -ne 0) { throw 'Search privacy settings failed.' }
    Get-Content -Raw (Join-Path $PSScriptRoot 'check-native-ranking.py') | docker compose exec -T search-provider /usr/local/searxng/.venv/bin/python -
    if ($LASTEXITCODE -ne 0) { throw 'Pinned ranking characterization changed; review before updating expectations.' }
    docker compose exec -T -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/usr/local/searxng search-provider /usr/local/searxng/.venv/bin/python /opt/anonexplo/test_date_merge.py
    if ($LASTEXITCODE -ne 0) { throw 'Publication-date merge regressions failed.' }
    # No upstream query: direct-IP connection must fail in the offline base.
    @'
import socket
try:
    with socket.create_connection(('1.1.1.1', 443), timeout=3):
        raise SystemExit('FAIL: base search has direct egress')
except OSError:
    print('PASS: base search cannot reach direct public HTTPS')
'@ | docker compose exec -T search-provider python -
    if ($LASTEXITCODE -ne 0) { throw 'Offline base leaked direct egress.' }
    $catalogue = Invoke-RestMethod -Uri 'http://127.0.0.1:18085/config' -TimeoutSec 10
    foreach ($entry in @(
        @{ Category='general'; Engines=@('brave','bing','yahoo','wikipedia') },
        @{ Category='news'; Engines=@('brave.news','duckduckgo news','reuters') },
        @{ Category='science'; Engines=@('arxiv','pubmed','crossref') }
    )) {
        $names = @($catalogue.engines | Where-Object { $_.enabled -and $entry.Category -in $_.categories } | ForEach-Object name)
        Assert-SetEquality $entry.Category $names $entry.Engines
    }
    Write-Host 'Testing isolated outage and recovery (no queries)...'
    try {
        docker compose stop search-provider
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop test search.' }
        $outage = $null
        try {
            Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:18085/' -TimeoutSec 15 -MaximumRedirection 0 | Out-Null
        } catch { $outage = $_.Exception.Response }
        if (-not $outage -or [int]$outage.StatusCode -ne 503 -or $outage.Headers['Location'] -or
            $outage.Headers['Cache-Control'] -ne 'no-store' -or $outage.Headers['Referrer-Policy'] -ne 'no-referrer') {
            throw 'Outage did not fail locally with privacy headers.'
        }
    } finally {
        docker compose up -d --no-deps --wait --wait-timeout 120 search-provider
        if ($LASTEXITCODE -ne 0) { throw 'Isolated recovery failed.' }
    }
    Assert-HttpPrivacy '/'
    if ((docker compose ps -q host-gateway) -ne $id) { throw 'Gateway replaced during recovery.' }
    Write-Host 'Validation passed: search-only topology, policies, offline tests, native UI and recovery.'
} finally {
    docker compose down --remove-orphans | Out-Null
    foreach ($key in $saved.Keys) { [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process') }
    Pop-Location
}

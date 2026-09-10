$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if (-not (Test-Path -LiteralPath 'data/preferences/shadow-domains.json')) { throw 'Local preferred domains are required; do not publish them.' }
    if (-not (Test-Path -LiteralPath 'data/models/bge-reranker-v2-m3/model.safetensors')) { throw 'Provision the pinned model explicitly first.' }
    & docker compose -f docker-compose.preview.yml config --quiet
    if ($LASTEXITCODE) { throw 'Preview configuration invalid.' }
    . (Join-Path $PSScriptRoot 'preview-policy.ps1')
    $raw = & docker compose -f docker-compose.preview.yml config --format json
    if ($LASTEXITCODE) { throw 'Preview configuration unavailable.' }
    Assert-PreviewPolicy ($raw | ConvertFrom-Json)
    & docker compose -f docker-compose.preview.yml up -d --wait --wait-timeout 180
    if ($LASTEXITCODE) { throw 'Preview unavailable. Normal searches remain unaffected.' }
    Write-Host 'Local preferred-source preview ready. Toggle on a General results page at 127.0.0.1:8085.'
} finally { Pop-Location }

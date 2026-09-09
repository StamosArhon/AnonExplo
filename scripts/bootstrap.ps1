$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envTemplate = Join-Path $root ".env.example"
$envTarget = Join-Path $root ".env"

if (-not (Test-Path $envTarget)) {
    Copy-Item -LiteralPath $envTemplate -Destination $envTarget
    $secret = -join ((48..57) + (97..102) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    (Get-Content -LiteralPath $envTarget) `
        -replace 'SEARXNG_SECRET=replace-with-local-random-secret', "SEARXNG_SECRET=$secret" `
        | Set-Content -LiteralPath $envTarget
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists; leaving it unchanged"
}

New-Item -ItemType Directory -Force -Path (Join-Path $root "data\searxng-cache") | Out-Null

Write-Host "Bootstrap complete."
Write-Host "Next steps:"
Write-Host "  1. Review .env"
Write-Host "  2. Import a separate Proton credential using scripts/import-proton-wireguard.ps1"
Write-Host "  3. Run powershell -ExecutionPolicy Bypass -File scripts/validate.ps1"
Write-Host "  4. Run powershell -ExecutionPolicy Bypass -File scripts/start-proton-search.ps1"
Write-Host "  5. Run powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1 after the stack is up"

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envTemplate = Join-Path $root ".env.example"
$envTarget = Join-Path $root ".env"

if (-not (Test-Path $envTarget)) {
    Copy-Item -LiteralPath $envTemplate -Destination $envTarget
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists; leaving it unchanged"
}

New-Item -ItemType Directory -Force -Path (Join-Path $root "data\models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root "data\searxng-cache") | Out-Null

Write-Host "Bootstrap complete."
Write-Host "Next steps:"
Write-Host "  1. Review .env"
Write-Host "  2. Provision a local model file before enabling the llamacpp profile"
Write-Host "  3. Run docker compose up --build ui backend fetcher search-provider"

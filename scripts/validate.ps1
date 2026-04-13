$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

try {
    Write-Host "Validating docker compose configuration..."
    docker compose config | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker compose config failed." }

    Write-Host "Building repo-managed images..."
    docker compose build ui backend fetcher
    if ($LASTEXITCODE -ne 0) { throw "docker compose build failed." }

    Write-Host "Running backend tests..."
    docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }

    Write-Host "Running fetcher tests..."
    docker compose run --rm --no-deps fetcher python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Fetcher tests failed." }

    Write-Host "Validation completed successfully."
} finally {
    Pop-Location
}

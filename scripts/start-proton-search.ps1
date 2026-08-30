param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = Join-Path $root ".env"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing .env. Copy .env.example to .env and set PROTON_WIREGUARD_PRIVATE_KEY first."
}

$keyLine = Get-Content -LiteralPath $envPath |
    Where-Object { $_ -match "^\s*PROTON_WIREGUARD_PRIVATE_KEY=(.+)$" } |
    Select-Object -First 1

if (-not $keyLine) {
    throw "PROTON_WIREGUARD_PRIVATE_KEY is missing from .env. Generate a separate Proton WireGuard configuration for this PC."
}

$privateKey = ($keyLine -replace "^\s*PROTON_WIREGUARD_PRIVATE_KEY=", "").Trim()
if (-not $privateKey -or $privateKey.StartsWith("replace-with-")) {
    throw "PROTON_WIREGUARD_PRIVATE_KEY is still a placeholder. Generate a separate Proton WireGuard configuration for this PC."
}

Push-Location $root
try {
    $composeArgs = @(
        "-f", "docker-compose.yml",
        "-f", "docker-compose.proton-search.yml",
        "--profile", "proton-search",
        "up", "-d"
    )

    if ($Build) {
        $composeArgs += "--build"
    }

    $composeArgs += @(
        "host-gateway",
        "ui",
        "backend",
        "fetcher",
        "search-provider",
        "search-vpn"
    )

    & docker compose @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "The Proton search profile failed to start. Inspect docker compose logs search-vpn search-provider."
    }

    Write-Host "AnonExplo search-only Proton VPN profile is running."
    Write-Host "Only search-provider shares the search-vpn network namespace; the rest of this PC is unchanged."
}
finally {
    Pop-Location
}

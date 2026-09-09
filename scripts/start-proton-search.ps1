param(
    [switch]$Build,
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$credentialPath = Join-Path $root 'data\proton\wireguard\wg0.conf'
if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
    throw 'Import a separate Proton configuration using scripts/import-proton-wireguard.ps1 first. No direct fallback is started.'
}
$resolverPath = Join-Path $root 'data\proton\resolv.conf'
if (-not (Test-Path -LiteralPath $resolverPath)) {
    Copy-Item -LiteralPath (Join-Path $root 'configs\searxng\resolv.vpn.conf') -Destination $resolverPath
}

Push-Location $root
try {
    $composeArgs = @(
        "-f", "docker-compose.yml",
        "-f", "docker-compose.proton-search.yml",
        "--profile", "proton-search",
        "up", "-d", "--wait", "--wait-timeout", "180"
    )

    if ($Build) {
        $composeArgs += "--build"
    }
    if ($Recreate) { $composeArgs += '--force-recreate' }

    $composeArgs += @(
        "host-gateway",
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

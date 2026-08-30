$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
    $composeArgs = @(
        "-f", "docker-compose.yml",
        "-f", "docker-compose.proton-search.yml",
        "--profile", "proton-search"
    )

    $vpnContainerId = (& docker compose @composeArgs ps -q search-vpn).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $vpnContainerId) {
        throw "The Proton search profile is not running. Start it with scripts/start-proton-search.ps1."
    }

    $vpnHealth = (& docker inspect $vpnContainerId --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}").Trim()
    if ($LASTEXITCODE -ne 0 -or $vpnHealth -ne "healthy") {
        throw "The search-vpn container is not healthy (status: $vpnHealth). Inspect its logs before searching."
    }

    $searchIp = (& docker compose @composeArgs exec -T search-provider python -c "import urllib.request; print(urllib.request.urlopen('https://api.ipify.org', timeout=10).read().decode().strip())").Trim()
    if ($LASTEXITCODE -ne 0 -or $searchIp -notmatch "^\d{1,3}(\.\d{1,3}){3}$") {
        throw "Could not determine the public IP used by search-provider."
    }

    $hostIp = $null
    try {
        $hostIp = (Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 10).ToString().Trim()
    }
    catch {
        $hostIp = "unavailable"
    }

    [pscustomobject]@{
        SearchProviderHealth = $vpnHealth
        SearchProviderPublicIp = $searchIp
        HostPublicIp = $hostIp
        UsesDifferentEgress = ($hostIp -ne "unavailable" -and $hostIp -ne $searchIp)
    } | Format-List

    if ($hostIp -ne "unavailable" -and $hostIp -eq $searchIp) {
        Write-Warning "The search-provider public IP matches the host IP. Verify that the Proton tunnel is active and that the host is not already using the same VPN endpoint."
    }
}
finally {
    Pop-Location
}

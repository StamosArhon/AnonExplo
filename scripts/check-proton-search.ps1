param([switch]$TestKillSwitch)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
$composeArgs = @('-f', 'docker-compose.yml', '-f', 'docker-compose.proton-search.yml', '--profile', 'proton-search')
function Invoke-SearchProbe([string]$Code) {
    $result = $Code | & docker compose @composeArgs exec -T search-provider python -
    if ($LASTEXITCODE -ne 0) { throw 'Search network probe failed.' }
    return ($result -join "`n").Trim()
}
try {
    $vpnId = [string](& docker compose @composeArgs ps -q search-vpn)
    if ($LASTEXITCODE -ne 0 -or -not $vpnId.Trim()) { throw 'VPN is not running.' }
    $searchId = [string](& docker compose @composeArgs ps -q search-provider)
    if ($LASTEXITCODE -ne 0 -or -not $searchId.Trim()) { throw 'Search is not running.' }
    $health = [string](& docker inspect $vpnId --format '{{.State.Health.Status}}')
    if ($LASTEXITCODE -ne 0 -or $health.Trim() -ne 'healthy') { throw 'VPN is not healthy.' }
    $mode = [string](& docker inspect $searchId --format '{{.HostConfig.NetworkMode}}')
    if ($LASTEXITCODE -ne 0 -or $mode.Trim() -ne "container:$($vpnId.Trim())") { throw 'Search is not sharing the VPN namespace.' }
    $searchIp = Invoke-SearchProbe @'
import pathlib, socket, urllib.request
nameservers = [line.split()[1] for line in pathlib.Path('/etc/resolv.conf').read_text().splitlines() if line.startswith('nameserver ')]
assert nameservers == ['127.0.0.1'], 'Search DNS is not pinned to the VPN resolver'
socket.getaddrinfo('example.com', 443)
with socket.create_connection(('1.1.1.1', 443), timeout=5):
    pass
print(urllib.request.urlopen('https://api.ipify.org', timeout=15).read().decode().strip())
'@
    $hostIp = [string](Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 15)
    if ($hostIp.Trim() -eq $searchIp) { throw 'Host and search IP match; distinct egress was not demonstrated.' }
    Write-Host 'PASS: VPN healthy, shared namespace, VPN-local DNS, working HTTPS, and different host/search egress.'
    if ($TestKillSwitch) {
        Write-Host 'Temporarily stopping only search-vpn to test fail-closed behavior...'
        try {
            & docker compose @composeArgs stop search-vpn
            if ($LASTEXITCODE -ne 0) { throw 'Could not stop the VPN for the test.' }
            $result = Invoke-SearchProbe @'
import socket
# Bypass DNS entirely: failure cannot be mistaken for just a dead resolver.
try:
    connection = socket.create_connection(('1.1.1.1', 443), timeout=4)
except OSError:
    pass
else:
    connection.close()
    raise SystemExit('FAIL: direct HTTPS egress worked while VPN was stopped')
# A valid example.com A query sent straight to a public resolver must also fail.
query = b'\x51\x72\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01'
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as resolver:
    resolver.settimeout(4)
    try:
        resolver.sendto(query, ('1.1.1.1', 53))
        resolver.recvfrom(4096)
    except OSError:
        pass
    else:
        raise SystemExit('FAIL: direct DNS egress worked while VPN was stopped')
try:
    with socket.create_connection(('2606:4700:4700::1111', 443), timeout=4):
        raise SystemExit('FAIL: IPv6 egress worked while VPN was stopped')
except OSError:
    pass
print('PASS: direct HTTPS, direct DNS, and IPv6 blocked with VPN stopped.')
'@
            Write-Host $result
        } finally {
            # Restarted VPN containers can get a new namespace: recreate clients.
            & (Join-Path $PSScriptRoot 'start-proton-search.ps1') -Recreate
            if ($LASTEXITCODE -ne 0) { throw 'VPN recovery failed; do not switch to direct search.' }
        }
        & (Join-Path $PSScriptRoot 'check-proton-search.ps1')
    }
} finally { Pop-Location }

param([object]$Base, [object]$Vpn)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'compose-policy.ps1')
$cases = @(
    @{Name='legacy service'; Vpn=$false; Mutate={param($c) $c.services | Add-Member NoteProperty ui @{} }},
    @{Name='public bind'; Vpn=$false; Mutate={param($c) $c.services.'host-gateway'.ports[0].host_ip='0.0.0.0' }},
    @{Name='legacy port'; Vpn=$false; Mutate={param($c) $c.services.'host-gateway'.ports[0].target=3000 }},
    @{Name='direct base egress'; Vpn=$false; Mutate={param($c) $c.services.'search-provider'.networks | Add-Member NoteProperty egress @{} }},
    @{Name='noninternal core'; Vpn=$false; Mutate={param($c) $c.networks.core_internal.internal=$false }},
    @{Name='writable root'; Vpn=$false; Mutate={param($c) $c.services.'search-provider'.read_only=$false }},
    @{Name='unpinned image'; Vpn=$false; Mutate={param($c) $c.services.'search-provider'.image='searxng/searxng:latest' }},
    @{Name='wrong namespace'; Vpn=$true; Mutate={param($c) $c.services.'search-provider'.network_mode='host' }},
    @{Name='wrong DNS'; Vpn=$true; Mutate={param($c) ($c.services.'search-provider'.volumes | Where-Object target -eq '/etc/resolv.conf').read_only=$false }},
    @{Name='key in environment'; Vpn=$true; Mutate={param($c) $c.services.'search-vpn'.environment | Add-Member NoteProperty WIREGUARD_PRIVATE_KEY forbidden }},
    @{Name='writable key'; Vpn=$true; Mutate={param($c) ($c.services.'search-vpn'.volumes | Where-Object target -eq '/gluetun/wireguard/wg0.conf').read_only=$false }},
    @{Name='public control API'; Vpn=$true; Mutate={param($c) $c.services.'search-vpn'.environment.HTTP_CONTROL_SERVER_ADDRESS='0.0.0.0:8000' }},
    @{Name='kill switch off'; Vpn=$true; Mutate={param($c) $c.services.'search-vpn'.environment | Add-Member NoteProperty FIREWALL off }},
    @{Name='extra capability'; Vpn=$true; Mutate={param($c) $c.services.'search-vpn'.cap_add += 'SYS_ADMIN' }}
)
foreach ($case in $cases) {
    $source = if ($case.Vpn) { $Vpn } else { $Base }
    $copy = $source | ConvertTo-Json -Depth 50 | ConvertFrom-Json
    & $case.Mutate $copy
    $rejected = $false
    try { Assert-SearchComposePolicy $copy '18085' -Vpn:$case.Vpn } catch { $rejected = $true }
    if (-not $rejected) { throw "Policy accepted regression: $($case.Name)" }
}
Write-Host "PASS: $($cases.Count) negative Compose policy tests."

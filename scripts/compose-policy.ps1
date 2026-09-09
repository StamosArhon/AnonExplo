function Get-NamedValue {
    param(
        [object]$Container,
        [string]$Name,
        [string]$Kind
    )

    $property = $Container.PSObject.Properties | Where-Object Name -eq $Name | Select-Object -First 1
    if (-not $property) {
        throw "Missing $Kind '$Name' in the compose configuration."
    }

    return $property.Value
}

function Get-NamedKeys {
    param([object]$Container)

    if ($null -eq $Container) {
        return @()
    }

    return @($Container.PSObject.Properties | ForEach-Object { $_.Name })
}

function Assert-SetEquality {
    param(
        [string]$Label,
        [string[]]$Actual,
        [string[]]$Expected
    )

    $normalizedActual = @($Actual | Sort-Object -Unique)
    $normalizedExpected = @($Expected | Sort-Object -Unique)

    if (($normalizedActual -join ",") -ne ($normalizedExpected -join ",")) {
        throw "$Label did not match. Expected '$($normalizedExpected -join ", ")' but found '$($normalizedActual -join ", ")'."
    }
}

function Test-DigestPinnedImage {
    param([string]$ImageReference)

    return $ImageReference -match "@sha256:[0-9a-f]{64}$"
}

function Assert-ServiceHasHealthcheck {
    param(
        [object]$ComposeConfig,
        [string]$ServiceName
    )

    $service = Get-NamedValue -Container $ComposeConfig.services -Name $ServiceName -Kind "service"
    $hasHealthcheck = $service.PSObject.Properties | Where-Object Name -eq "healthcheck" | Select-Object -First 1
    if (-not $hasHealthcheck) {
        throw "Service '$ServiceName' is missing a healthcheck."
    }
}

function Assert-ServiceSecurityDefaults {
    param(
        [object]$ComposeConfig,
        [string]$ServiceName
    )

    $service = Get-NamedValue -Container $ComposeConfig.services -Name $ServiceName -Kind "service"

    if (-not $service.read_only) {
        throw "Service '$ServiceName' must be read-only by default."
    }

    if ($service.cap_drop -notcontains "ALL") {
        throw "Service '$ServiceName' must drop all Linux capabilities by default."
    }

    if ($service.security_opt -notcontains "no-new-privileges:true") {
        throw "Service '$ServiceName' must enable no-new-privileges."
    }
}


function Assert-SearchComposePolicy {
    param([object]$Config, [string]$Port, [switch]$Vpn)
    $expected = @('host-gateway', 'search-provider')
    if ($Vpn) { $expected += 'search-vpn' }
    Assert-SetEquality 'Search-only service set' (Get-NamedKeys $Config.services) $expected
    if (-not $Config.networks.core_internal.internal) { throw 'Core network must be internal.' }
    $gateway = $Config.services.'host-gateway'
    if (@($gateway.ports).Count -ne 1 -or $gateway.ports[0].target -ne 8085 -or
        $gateway.ports[0].published -ne $Port -or $gateway.ports[0].host_ip -ne '127.0.0.1') {
        throw 'Only the localhost search port may be published.'
    }
    if ($gateway.user -ne '101:101') { throw 'Gateway must be unprivileged.' }
    Assert-SetEquality 'Gateway networks' (Get-NamedKeys $gateway.networks) @('core_internal','host_access')
    foreach ($name in $expected) {
        $service = $Config.services.$name
        Assert-ServiceSecurityDefaults $Config $name
        Assert-ServiceHasHealthcheck $Config $name
        if (-not (Test-DigestPinnedImage $service.image)) { throw "Unpinned image: $name" }
        if ($service.privileged) { throw "Privileged service: $name" }
        if ($name -ne 'search-vpn' -and $service.cap_add) { throw "Unexpected capabilities: $name" }
        if ($name -ne 'host-gateway' -and $service.ports) { throw "Unexpected publication: $name" }
        $deps = @(Get-NamedKeys $service.depends_on)
        if (@($deps | Where-Object { $_ -notin $expected }).Count) { throw "Legacy dependency: $name" }
    }
    $search = $Config.services.'search-provider'
    if ($Vpn) {
        Assert-ProtonSearchComposePolicy $Config
        Assert-SetEquality 'VPN capabilities' $Config.services.'search-vpn'.cap_add @('NET_ADMIN')
        if ($Config.services.'search-vpn'.environment.FIREWALL -eq 'off') { throw 'Kill switch disabled.' }
        if ($search.depends_on.'search-vpn'.condition -ne 'service_healthy') { throw 'Search must wait for VPN health.' }
    } else {
        Assert-SetEquality 'Offline search networks' (Get-NamedKeys $search.networks) @('core_internal')
        if ($search.network_mode) { throw 'Unexpected base namespace.' }
    }
}
function Assert-ProtonSearchComposePolicy {
    param([object]$ComposeConfig)

    $vpn = Get-NamedValue -Container $ComposeConfig.services -Name "search-vpn" -Kind "service"
    if (-not (Test-DigestPinnedImage -ImageReference $vpn.image)) {
        throw "Service 'search-vpn' must use a digest-pinned image reference."
    }

    if ($vpn.cap_add -notcontains "NET_ADMIN") {
        throw "Service 'search-vpn' must have NET_ADMIN to establish the tunnel."
    }

    if ($vpn.cap_drop -notcontains "ALL") {
        throw "Service 'search-vpn' must drop all capabilities before adding NET_ADMIN."
    }

    if (-not $vpn.read_only) {
        throw "Service 'search-vpn' must use a read-only root filesystem."
    }

    if ($vpn.security_opt -notcontains "no-new-privileges:true") {
        throw "Service 'search-vpn' must enable no-new-privileges."
    }

    if (($vpn.PSObject.Properties | Where-Object Name -eq "ports" | Select-Object -First 1) -and $vpn.ports) {
        throw "Service 'search-vpn' must not publish a host port."
    }

    $tunDevice = @($vpn.devices | Where-Object { $_.target -eq "/dev/net/tun" }) | Select-Object -First 1
    if (-not $tunDevice) {
        throw "Service 'search-vpn' must expose /dev/net/tun."
    }

    Assert-SetEquality `
        -Label "Service 'search-vpn' networks" `
        -Actual (Get-NamedKeys -Container $vpn.networks) `
        -Expected @("core_internal", "egress")

    Assert-ServiceHasHealthcheck -ComposeConfig $ComposeConfig -ServiceName "search-vpn"
    if (($vpn.healthcheck.test -join ' ') -notmatch 'healthcheck && nslookup example.com 127.0.0.1') {
        throw 'VPN health must check both the tunnel and VPN-local DNS.'
    }
    if ($vpn.environment.HTTP_CONTROL_SERVER_ADDRESS -ne '127.0.0.1:8000') {
        throw 'VPN control API must listen only inside the shared namespace.'
    }
    if ($vpn.environment.PSObject.Properties.Name -contains 'WIREGUARD_PRIVATE_KEY') {
        throw 'VPN credentials must not be present in Compose environment metadata.'
    }
    $keyMount = @($vpn.volumes | Where-Object target -eq '/gluetun/wireguard/wg0.conf')
    if ($keyMount.Count -ne 1 -or -not $keyMount[0].read_only -or $keyMount[0].bind.create_host_path) {
        throw 'VPN must use a read-only, explicitly provisioned credential file.'
    }

    $searchProvider = Get-NamedValue -Container $ComposeConfig.services -Name "search-provider" -Kind "service"
    $dnsMount = @($searchProvider.volumes | Where-Object target -eq '/etc/resolv.conf')
    if ($dnsMount.Count -ne 1 -or -not $dnsMount[0].read_only -or $dnsMount[0].source -notmatch 'resolv\.vpn\.conf$') {
        throw 'Search DNS must be pinned to the VPN-local resolver, not Docker DNS.'
    }
    if ($searchProvider.network_mode -ne "service:search-vpn") {
        throw "The Proton search profile must place search-provider in the search-vpn network namespace."
    }

    if ($searchProvider.PSObject.Properties | Where-Object Name -eq "networks" | Select-Object -First 1) {
        throw "The Proton search profile must remove direct network attachments from search-provider."
    }

    $gateway = Get-NamedValue -Container $ComposeConfig.services -Name "host-gateway" -Kind "service"
    $gatewayConfig = @($gateway.volumes | Where-Object { $_.target -eq "/etc/nginx/nginx.conf" }) | Select-Object -First 1
    if (-not $gatewayConfig -or $gatewayConfig.source -notmatch "nginx\.proton-search\.conf$") {
        throw "The Proton search profile must use the VPN-aware localhost gateway configuration."
    }
}

function Get-ManifestPlatform([object]$Descriptor) {
    if ($Descriptor.mediaType -notin @('application/vnd.oci.image.manifest.v1+json',
        'application/vnd.docker.distribution.manifest.v2+json') -or
        $Descriptor.digest -notmatch '^sha256:[0-9a-f]{64}$' -or
        $Descriptor.platform.os -ne 'linux' -or
        $Descriptor.platform.architecture -notmatch '^[a-z0-9]+$') {
        throw 'Missing or invalid platform manifest; a tag/index alone is insufficient.'
    }
    $platform = "linux/$($Descriptor.platform.architecture)"
    if ($Descriptor.platform.variant) {
        if ($Descriptor.platform.variant -notmatch '^[a-z0-9]+$') { throw 'Invalid platform variant.' }
        $platform += "/$($Descriptor.platform.variant)"
    }
    return $platform
}

function Assert-SameRuntimeManifest([object]$Running, [object]$Built) {
    $platform = Get-ManifestPlatform $Running
    if ((Get-ManifestPlatform $Built) -ne $platform -or $Running.digest -ne $Built.digest) {
        throw 'Deployed search platform manifest differs from the local repair build; review deployment.'
    }
}

function Assert-PreviewPolicy($config) {
    if ($config.name -ne 'anonexplo-preview' -or @($config.services.PSObject.Properties).Count -ne 1) { throw 'Unexpected preview project/services.' }
    $s = $config.services.reranker
    if ($s.image -ne 'sha256:a1ecd793732ada795e0f2fb5162b126b748a982ca902a5a7513df946f2b5cb99' -or
        $s.pull_policy -ne 'never' -or $s.build -or $s.network_mode -ne 'none' -or $s.networks -or $s.ports -or
        $s.privileged -or $s.cap_add -or -not $s.read_only -or $s.user -ne '65534:65534' -or
        ($s.cap_drop -join ',') -ne 'ALL' -or ($s.security_opt -join ',') -ne 'no-new-privileges:true' -or
        $s.logging.driver -ne 'none' -or -not $s.healthcheck -or $s.pids_limit -ne 256 -or $s.cpus -ne 8 -or
        $s.mem_limit -ne 12884901888) { throw 'Preview isolation boundary invalid.' }
    $targets = @($s.volumes | ForEach-Object target | Sort-Object)
    if (($targets -join ',') -ne '/model,/preferences/domains.json,/run/anonexplo-preview,/trial') { throw 'Unexpected preview mounts.' }
    foreach ($v in $s.volumes) {
        if ($v.target -ne '/run/anonexplo-preview' -and ($v.type -ne 'bind' -or -not $v.read_only)) { throw 'Preview input must be read-only.' }
    }
    if (-not $config.volumes.socket.external -or $config.volumes.socket.name -ne 'anonexplo_preview_socket') { throw 'Unexpected socket volume.' }
    foreach ($key in @('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK')) {
        if ($s.environment.$key -ne '1') { throw 'Offline model environment missing.' }
    }
}

param([switch]$Live, [switch]$ReviewTop5)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$image = 'searxng/searxng:latest@sha256:3547509b419cd6a67333d6d68bd1ffad8d46d3669d82e7a7bd538f7b45827432'
Push-Location $root
try {
    if ($ReviewTop5 -and -not $Live) { throw 'ReviewTop5 requires the explicit live trial.' }
    $network = 'none'
    $script = '/experiment/check-news-candidate.py'
    $name = 'anonexplo-news-candidate-offline'
    $extra = @()
    if ($Live) {
        # Operator prerequisite: review preceding degradation/cooldowns. Never
        # rerun this disposable process to reset a ban or retry a failed query.
        # Native error history has no suspension expiry timestamp. Refuse
        # long-ban classes; for known timeout/rate-limit history wait a full
        # configured rate-limit interval and abort if that history changes.
        # This is not proof of browser inactivity: the operator must avoid
        # concurrent searches. No upstream request is made by these reads.
        function Read-NewsErrorState {
            $history = Invoke-RestMethod -Uri 'http://127.0.0.1:8085/stats/errors' -TimeoutSec 10 -MaximumRedirection 0
            $selected = [ordered]@{}
            foreach ($engine in @('brave','brave.news','duckduckgo','duckduckgo news','reuters')) {
                $selected[$engine] = $history.$engine
                foreach ($entry in $history.$engine) {
                    if ($entry.exception_classname -and $entry.exception_classname -notin @(
                        'curl_cffi.requests.exceptions.Timeout', 'searx.exceptions.SearxEngineTooManyRequestsException')) {
                        throw 'Unreviewed or long-ban error history; diagnose before a disposable trial.'
                    }
                }
            }
            return ($selected | ConvertTo-Json -Depth 12 -Compress)
        }
        # Allow a request already in flight at quiet-window confirmation to
        # finish before the baseline. The pinned maximum engine budget is 8s;
        # this does not reset suspension or weaken the subsequent 180s check.
        Write-Host 'Allowing 10 seconds for in-flight requests to settle before the error-history baseline.'
        Start-Sleep -Seconds 10
        $before = Read-NewsErrorState
        Write-Host 'Please avoid concurrent browser searches. Waiting 180 seconds for known timeout/rate-limit cooldowns; no provider polling.'
        foreach ($interval in 1..6) { Start-Sleep -Seconds 30 }
        if ((Read-NewsErrorState) -ne $before) { throw 'Engine error history changed during cooldown; trial not sent.' }
        & (Join-Path $PSScriptRoot 'check-proton-search.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'VPN verification failed.' }
        $compose = @('-f','docker-compose.yml','-f','docker-compose.proton-search.yml','--profile','proton-search')
        $vpn = [string](& docker compose @compose ps -q search-vpn)
        if ($LASTEXITCODE -ne 0 -or -not $vpn.Trim()) { throw 'VPN namespace unavailable.' }
        $search = [string](& docker compose @compose ps -q search-provider)
        if ($LASTEXITCODE -ne 0 -or -not $search.Trim()) { throw 'Production search unavailable.' }
        $deployedImage = [string](& docker inspect $search.Trim() --format '{{.Image}}')
        if ($LASTEXITCODE -ne 0) { throw 'Production image check failed.' }
        $candidateImage = [string](& docker image inspect $image --format '{{.Id}}')
        if ($LASTEXITCODE -ne 0 -or $deployedImage -ne $candidateImage) { throw 'Candidate image differs from production; review version before trial.' }
        $network = "container:$($vpn.Trim())"
        $script = '/experiment/run-news-candidate.py'
        $name = 'anonexplo-news-candidate-live'
        $extra = @('--mount', "type=bind,source=$root/configs/searxng/resolv.vpn.conf,target=/etc/resolv.conf,readonly")
        Write-Host 'One bounded live trial: four distinct public queries at 20s spacing, stop on first degradation. No retries or production changes.'
    }
    $existing = docker ps -aq --filter "name=^/$name$"
    if ($LASTEXITCODE -ne 0 -or $existing) { throw 'Candidate name already exists or Docker inspection failed; refusing replacement.' }
    $run = @('run','--rm','--name',$name,'--pull','never','--network',$network,
        '--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--log-driver','none','--memory','768m','--cpus','1','--pids-limit','128',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=64m,mode=1777',
        '--tmpfs','/var/cache/searxng:rw,noexec,nosuid,size=64m,mode=1777',
        '--env','PYTHONDONTWRITEBYTECODE=1','--env','PYTHONPATH=/usr/local/searxng',
        '--env','HTTP_PROXY=','--env','HTTPS_PROXY=','--env','ALL_PROXY=',
        '--env','http_proxy=','--env','https_proxy=','--env','all_proxy=',
        '--env','SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml',
        '--mount',"type=bind,source=$root/configs/searxng/settings.yml,target=/etc/searxng/settings.yml,readonly",
        '--mount',"type=bind,source=$PSScriptRoot,target=/experiment,readonly",
        '--entrypoint','/usr/local/searxng/.venv/bin/python')
    $run += $extra
    $run += @($image,$script)
    if ($ReviewTop5) { $run += '--review-top5' }
    & docker @run
    if ($LASTEXITCODE -ne 0) { throw 'Candidate stopped or failed. Do not retry automatically; review sanitized evidence.' }
    if (-not $Live) {
        $run[-1] = '/experiment/run-news-candidate.py'
        $run += '--self-check'
        & docker @run
        if ($LASTEXITCODE -ne 0) { throw 'Offline candidate initialization failed; no queries were sent.' }
    }
} finally { Pop-Location }

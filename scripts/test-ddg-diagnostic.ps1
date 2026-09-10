param([switch]$Live, [ValidateSet('anonexplo/searxng:date-merge-v1','anonexplo/searxng:validation')][string]$Image = 'anonexplo/searxng:date-merge-v1')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if ($Live) {
        throw 'Completed diagnostic stopped on token HTTP timeout. Do not retry its fixtures; review a separately scoped transport diagnostic first.'
    }
    $network = 'none'
    $extra = @()
    $compose = @('-f','docker-compose.yml','-f','docker-compose.proton-search.yml','--profile','proton-search')
    if ($Live) {
        function Read-DdgState {
            $stats = Invoke-RestMethod -Uri 'http://127.0.0.1:8085/stats/errors' -TimeoutSec 10 -MaximumRedirection 0
            $selected = [ordered]@{}
            foreach ($engine in @('duckduckgo','duckduckgo news')) {
                $selected[$engine] = $stats.$engine
                foreach ($entry in $stats.$engine) {
                    if ($entry.exception_classname -and $entry.exception_classname -notin @(
                        'curl_cffi.requests.exceptions.Timeout', 'searx.exceptions.SearxEngineTooManyRequestsException',
                        'searx.exceptions.SearxEngineAccessDeniedException')) {
                        throw 'Unreviewed DDG error class: no diagnostic query sent.'
                    }
                }
            }
            return ($selected | ConvertTo-Json -Depth 12 -Compress)
        }
        Write-Host 'Avoid concurrent searches: allowing 10s settling then a full 180s DDG cooldown. No provider polling.'
        Start-Sleep -Seconds 10
        $before = Read-DdgState
        foreach ($interval in 1..6) { Start-Sleep -Seconds 30; Write-Host "Cooldown $($interval * 30)/180s" }
        if ((Read-DdgState) -ne $before) { throw 'DDG history changed; diagnostic not sent. Do not automatically retry.' }
        & (Join-Path $PSScriptRoot 'ops-check.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Production/VPN verification failed.' }
        $vpn = [string](& docker compose @compose ps -q search-vpn)
        if ($LASTEXITCODE -ne 0 -or -not $vpn.Trim()) { throw 'VPN unavailable.' }
        $network = "container:$($vpn.Trim())"
        $extra = @('--mount', "type=bind,source=$root/configs/searxng/resolv.vpn.conf,target=/etc/resolv.conf,readonly")
    }
    $name = 'anonexplo-ddg-diagnostic'
    $existing = docker ps -aq --filter "name=^/$name$"
    if ($LASTEXITCODE -ne 0 -or $existing) { throw 'Diagnostic name already exists or inspection failed; refusing replacement.' }
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
        '--mount',"type=bind,source=$PSScriptRoot,target=/diagnostic,readonly",
        '--entrypoint','/usr/local/searxng/.venv/bin/python')
    $run += $extra
    $run += @($image,'/diagnostic/run-ddg-diagnostic.py')
    if ($Live) { $run += '--live' }
    & docker @run
    if ($LASTEXITCODE -ne 0) { throw 'Diagnostic stopped or failed; review metadata, do not repeat automatically.' }
} finally { Pop-Location }

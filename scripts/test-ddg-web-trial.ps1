param([switch]$Live, [ValidateSet('anonexplo/searxng:date-merge-v1','anonexplo/searxng:validation')][string]$Image='anonexplo/searxng:date-merge-v1')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $root 'build/ddg-web-review/duckduckgo_web.py'
if (-not (Test-Path -LiteralPath $source)) { throw 'Provision the frozen upstream source explicitly first.' }
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'e3cf8fe33807c62d504a2b39e790e38ce6353850a367816fbdcce6c441ee7f73') { throw 'Upstream source mismatch.' }
if ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'ddg_web_trial.py') -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'e7ed615ba8de830dec6e09a506677d6be9db1518c4a6ee414e56486218a79175') { throw 'Frozen fixture/policy file changed; refuse evaluation.' }
if ($Live -and $Image -ne 'anonexplo/searxng:date-merge-v1') { throw 'Live trial requires verified production image.' }
$network = 'none'
$extra = @()
$name = 'anonexplo-ddg-web-trial'
$marker = Join-Path $root 'build/ddg-web-trial-v1.attempted'
if ($Live -and (Test-Path -LiteralPath $marker)) { throw 'This one-shot trial was already attempted. Do not retry or delete its marker.' }
function Read-TrialState {
    $history = Invoke-RestMethod -Uri 'http://127.0.0.1:8085/stats/errors' -TimeoutSec 10 -MaximumRedirection 0
    $selected = [ordered]@{}
    foreach ($engine in @('duckduckgo','duckduckgo news')) {
        $selected[$engine] = $history.$engine
        foreach ($entry in $history.$engine) {
            if ($entry.exception_classname -notin @('curl_cffi.requests.exceptions.Timeout',
                    'searx.exceptions.SearxEngineTooManyRequestsException',
                    'searx.exceptions.SearxEngineAccessDeniedException')) { throw 'Unknown/long-ban DDG error history; no trial sent.' }
        }
    }
    # Compare in memory only. Never print raw error records or store payloads.
    $stats = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8085/stats' -TimeoutSec 10 -MaximumRedirection 0
    return (($selected | ConvertTo-Json -Depth 12 -Compress) + $stats.Content)
}
Push-Location $root
try {
    if ($Live) {
        Write-Host 'Avoid concurrent browser searches. Settling for 10s, then checking a full 180s quiet/cooldown window; no provider polling.'
        Start-Sleep -Seconds 10
        $before = Read-TrialState
        foreach ($interval in 1..6) { Start-Sleep -Seconds 30; Write-Host "Local cooldown wait $($interval * 30)/180s" }
        if ((Read-TrialState) -ne $before) { throw 'Local error/stats state changed; trial not sent. Do not automatically repeat.' }
        & (Join-Path $PSScriptRoot 'ops-check.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'VPN/production preflight failed.' }
        $compose = @('-f','docker-compose.yml','-f','docker-compose.proton-search.yml','--profile','proton-search')
        $vpn = [string](& docker compose @compose ps -q search-vpn)
        if ($LASTEXITCODE -ne 0 -or -not $vpn.Trim()) { throw 'VPN namespace unavailable.' }
        $network = "container:$($vpn.Trim())"
        $extra = @('--mount',"type=bind,source=$root/configs/searxng/resolv.vpn.conf,target=/etc/resolv.conf,readonly",
            '--env','ANONEXPLO_WEB_TRIAL_AUTHORIZED=frozen-web-trial-v1')
        if ((Read-TrialState) -ne $before) { throw 'Search activity changed during preflight; no trial sent.' }
    }
    $existing = docker ps -aq --filter "name=^/$name$"
    if ($LASTEXITCODE -ne 0 -or $existing) { throw 'Trial container already exists or inspection failed; refusing replacement.' }
    $run = @('run','--rm','--name',$name,'--pull','never','--network',$network,
        '--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--log-driver','none','--memory','768m','--cpus','1','--pids-limit','128',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=64m,mode=1777',
        '--env','PYTHONDONTWRITEBYTECODE=1','--env','PYTHONPATH=/usr/local/searxng',
        '--env','HTTP_PROXY=','--env','HTTPS_PROXY=','--env','ALL_PROXY=',
        '--env','http_proxy=','--env','https_proxy=','--env','all_proxy=',
        '--env','SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml',
        '--mount',"type=bind,source=$root/configs/searxng/settings.yml,target=/etc/searxng/settings.yml,readonly",
        '--mount',"type=bind,source=$source,target=/upstream/duckduckgo_web.py,readonly",
        '--mount',"type=bind,source=$PSScriptRoot,target=/diagnostic,readonly",
        '--entrypoint','/usr/local/searxng/.venv/bin/python')
    $run += $extra
    $run += @($Image,'/diagnostic/run-ddg-web-trial.py')
    if ($Live) {
        # Atomic one-shot guard. Empty marker contains no query, result or token.
        $handle = [System.IO.File]::Open($marker, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $handle.Dispose()
        $run += '--live'
    }
    & docker @run
    if ($LASTEXITCODE -ne 0) { throw 'Trial stopped/failed; do not retry. Review sanitized metrics only.' }
} finally { Pop-Location }

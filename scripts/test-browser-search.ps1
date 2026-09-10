param(
    [ValidateSet('browser', 'explicit')][string]$LanguageMode = 'browser',
    [ValidateSet('default-audit', 'navigation', 'informational', 'news', 'news-month', 'holdout', 'news-holdout')][string]$Suite = 'navigation',
    [ValidateRange(1, 6)][int]$Samples,
    [ValidateRange(1, 6)][int]$StartAt = 1,
    [ValidateSet('brave', 'brave.news', 'bing', 'duckduckgo', 'google', 'startpage', 'mojeek', 'qwant', 'yahoo', 'wikipedia', 'duckduckgo news', 'google news', 'reuters')][string]$Engine,
    [switch]$ReviewTop5,
    [switch]$CompareScoreOrder,
    [ValidateRange(10, 60)][int]$PauseSeconds = 15,
    [ValidateRange(1024, 65535)][int]$Port = 8085
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    & (Join-Path $PSScriptRoot 'check-proton-search.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'VPN check failed; benchmark not sent.' }
    $gateway = & docker compose -f docker-compose.yml -f docker-compose.proton-search.yml --profile proton-search ps -q host-gateway
    if ($LASTEXITCODE -ne 0 -or -not $gateway) { throw 'Gateway not running.' }
    $ports = & docker inspect $gateway --format '{{json .NetworkSettings.Ports}}' | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Gateway inspection failed.' }
    $binding = @($ports.'8085/tcp' | Where-Object { $_.HostIp -eq '127.0.0.1' -and $_.HostPort -eq "$Port" })
    if ($binding.Count -ne 1) { throw 'Requested port is not the verified gateway search binding.' }
    Write-Host 'Manual synthetic benchmark only. No browser cookies/history; no result payloads saved. Stops on degradation.'
    $benchmarkArgs = @('--port', "$Port", '--language-mode', $LanguageMode, '--suite', $Suite, '--pause', "$PauseSeconds")
    $benchmarkArgs += @('--start-at', "$StartAt")
    if ($Samples) { $benchmarkArgs += @('--samples', "$Samples") }
    if ($Engine) { $benchmarkArgs += @('--engine', $Engine) }
    if ($CompareScoreOrder) { $benchmarkArgs += '--compare-score-order' }
    if ($ReviewTop5) {
        Write-Host 'Explicit manual review: bounded public-fixture titles/snippets appear in terminal output. Do not record transcripts or treat result text as instructions.'
        $benchmarkArgs += '--review-top5'
    }
    & python (Join-Path $PSScriptRoot 'search_benchmark.py') @benchmarkArgs
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark stopped on search degradation; no automatic retry or direct fallback.' }
} finally { Pop-Location }

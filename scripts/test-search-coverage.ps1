param(
    [ValidateNotNullOrEmpty()][string[]]$Engines = @('brave', 'bing', 'yahoo'),
    [ValidateSet('navigation', 'informational', 'news', 'news-month', 'holdout', 'news-holdout')][string]$Suite = 'navigation',
    [ValidateRange(1, 6)][int]$Samples = 3,
    [ValidateRange(1024, 65535)][int]$Port = 8085
)
$ErrorActionPreference = 'Stop'
# Compatibility entry point: use the single, hardened benchmark implementation.
# Selection is explicit; no category/engine union, raw exception dumps, proxy
# inheritance or redirects. A degraded sample stops the entire invocation.
foreach ($engine in $Engines) {
    & (Join-Path $PSScriptRoot 'test-browser-search.ps1') -Engine $engine -Suite $Suite -Samples $Samples -Port $Port -LanguageMode explicit
    if ($LASTEXITCODE -ne 0) { throw 'Coverage test stopped; no retries or direct fallback.' }
    if ($engine -ne $Engines[-1]) { Start-Sleep -Seconds 15 }
}

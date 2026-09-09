param(
    [ValidateNotNullOrEmpty()][string[]]$Engines = @('brave', 'bing', 'yahoo'),
    [ValidateRange(1, 3)][int]$Samples = 3,
    [ValidateRange(1024, 65535)][int]$Port = 8085
)

$ErrorActionPreference = 'Stop'
# Deliberately synthetic, public fixtures, never browser history or user prompts.
# Output contains counts/host-match metrics only; no result bodies or URLs saved.
# "National Archaeological Museum" in Greek; JSON escapes keep PowerShell 5.1
# compatible with this UTF-8-without-BOM source file on Windows.
$greekQuery = '"\u03b5\u03b8\u03bd\u03b9\u03ba\u03cc \u03b1\u03c1\u03c7\u03b1\u03b9\u03bf\u03bb\u03bf\u03b3\u03b9\u03ba\u03cc \u03bc\u03bf\u03c5\u03c3\u03b5\u03af\u03bf"' | ConvertFrom-Json
$fixtures = @(
    @{ Id = 'navigation'; Query = 'Python programming language'; Language = 'en'; ExpectedHost = 'python.org' },
    @{ Id = 'technical'; Query = 'Docker Compose networking service network_mode'; Language = 'en'; ExpectedHost = 'docs.docker.com' },
    @{ Id = 'greek'; Query = $greekQuery; Language = 'el'; ExpectedHost = 'namuseum.gr' }
)

& (Join-Path $PSScriptRoot 'check-proton-search.ps1')
if ($LASTEXITCODE -ne 0) { throw 'VPN check failed; no search tests sent.' }
$base = "http://127.0.0.1:$Port"
$config = Invoke-RestMethod -Uri "$base/config" -TimeoutSec 10
foreach ($engine in $Engines) {
    if ($engine -notin @($config.engines | ForEach-Object { $_.name })) {
        throw "Engine '$engine' is not loaded. Add it as disabled in the catalogue before testing."
    }
}
foreach ($engine in $Engines) {
    foreach ($fixture in ($fixtures | Select-Object -First $Samples)) {
        $timer = [Diagnostics.Stopwatch]::StartNew()
        # POST keeps the fixture out of the local request URL. Never retry a
        # denied/CAPTCHA/rate-limited engine or clear its suspension for this test.
        $payload = @{
            q = $fixture.Query; format = 'json'; engines = $engine
            language = $fixture.Language; pageno = '1'
        }
        $response = Invoke-RestMethod -Method Post -Uri "$base/search" -Body $payload -TimeoutSec 20
        $timer.Stop()
        $results = @($response.results)
        $hosts = @($results | ForEach-Object { ([uri]$_.url).DnsSafeHost })
        $topHosts = @($hosts | Select-Object -First 5)
        $expected = $fixture.ExpectedHost
        $match = @($topHosts | Where-Object { $_ -eq $expected -or $_.EndsWith(".$expected") }).Count -gt 0
        $errors = @($response.unresponsive_engines | ForEach-Object { $_ -join ': ' })
        $contributors = @($results | ForEach-Object { $_.engines } | Sort-Object -Unique)
        if (@($contributors | Where-Object { $_ -ne $engine }).Count -gt 0) {
            throw 'Unexpected engine contributed results; sample isolation failed.'
        }
        [pscustomobject]@{
            Engine = $engine; Sample = $fixture.Id; Results = $results.Count
            Domains = @($hosts | Sort-Object -Unique).Count; ExpectedTop5 = $match
            Seconds = [math]::Round($timer.Elapsed.TotalSeconds, 2)
            Errors = $errors -join '; '
        } | ConvertTo-Json -Compress
        if ($errors.Count -gt 0) { break }
        Start-Sleep -Seconds 2
    }
}

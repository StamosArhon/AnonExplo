$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'setup-browser-search.ps1'
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Setup script does not parse.' }
# Extract only the generator function; never execute registration/browser setup.
$definition = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Write-LocalHelperFiles'}, $true)
if (-not $definition) { throw 'Missing helper generator.' }
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$helperDir = Join-Path $tempBase ('anonexplo-startup-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $helperDir | Out-Null
try {
    $root = Join-Path $helperDir "repo's copy"
    $startupScript = Join-Path $helperDir 'start.ps1'
    $startupLauncher = Join-Path $helperDir 'start.vbs'
    $dockerDesktopLauncher = Join-Path $helperDir 'docker.vbs'
    $configureScript = Join-Path $helperDir 'configure.js'
    $SearxngPort = 18085
    $NoDockerDesktopStart = $true
    . ([scriptblock]::Create($definition.Extent.Text))
    Write-LocalHelperFiles
    [System.Management.Automation.Language.Parser]::ParseFile($startupScript, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count) { throw 'Generated startup script does not parse (including quoted paths).' }
    $body = Get-Content -LiteralPath $startupScript -Raw
    if ($body -match '\bUI_PORT\b|\bBACKEND_PORT\b|docker compose|search-fallback\.js' -or
        $body -notmatch 'start-proton-search.ps1' -or -not $body.Contains('$startDockerIfNeeded = $false')) {
        throw 'Generated startup reintroduced legacy/direct-egress behavior.'
    }
    $launcher = Get-Content -LiteralPath $startupLauncher -Raw
    if ($launcher -notmatch '-WindowStyle Hidden' -or $launcher -notmatch ', 0, False') { throw 'Startup must stay hidden.' }
    node --check $configureScript
    if ($LASTEXITCODE -ne 0) { throw 'Preserved browser setup helper has a syntax error.' }
    $NoDockerDesktopStart = $false
    Write-LocalHelperFiles
    if (-not (Get-Content -LiteralPath $startupScript -Raw).Contains('$startDockerIfNeeded = $true')) { throw 'Docker startup switch failed.' }
    Write-Host 'PASS: generated startup syntax, quoted paths, VPN-only dispatch, hidden launchers, Docker switch and browser-helper syntax.'
} finally {
    $resolved = [IO.Path]::GetFullPath($helperDir)
    if (-not $resolved.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($resolved) -notmatch '^anonexplo-startup-test-[a-f0-9]{32}$') { throw 'Unsafe test cleanup path.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

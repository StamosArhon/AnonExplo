param([switch]$LiveReview)
$ErrorActionPreference = 'Stop'
if ($LiveReview) { throw 'Completed assessment stopped on provider degradation. Live review is retired; no retry.' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $LiveReview) {
    & python (Join-Path $PSScriptRoot 'quality_assessment.py')
    exit $LASTEXITCODE
}
if (Test-Path -LiteralPath (Join-Path $root 'build/quality-assessment-v1.attempted')) {
    throw 'One-shot assessment already attempted; no retry or suffix resume.'
}
Push-Location $root
try {
    & (Join-Path $PSScriptRoot 'ops-check.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Production/VPN preflight failed.' }
    $env:ANONEXPLO_QUALITY_PREFLIGHT = 'approved-v1'
    & python (Join-Path $PSScriptRoot 'quality_assessment.py') --live-review
    if ($LASTEXITCODE -ne 0) { throw 'Assessment stopped; no automatic retry.' }
} finally {
    Remove-Item Env:ANONEXPLO_QUALITY_PREFLIGHT -ErrorAction SilentlyContinue
    Pop-Location
}

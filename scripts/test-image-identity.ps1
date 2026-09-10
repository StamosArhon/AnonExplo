$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'image-identity.ps1')
$original = @{mediaType='application/vnd.oci.image.manifest.v1+json'; digest=('sha256:' + ('a' * 64)); platform=@{os='linux'; architecture='amd64'}}
Assert-SameRuntimeManifest $original $original
$cases = @(
    {param($d) $d.digest = 'sha256:' + ('b' * 64)},
    {param($d) $d.digest = 'tag-only'},
    {param($d) $d.platform.architecture = 'arm64'},
    {param($d) $d.mediaType = 'application/vnd.oci.image.index.v1+json'},
    {param($d) $d.platform.os = 'windows'},
    {param($d) $d.platform.architecture = '../amd64'},
    {param($d) $d.platform = $null}
)
foreach ($mutate in $cases) {
    $copy = $original | ConvertTo-Json -Depth 5 | ConvertFrom-Json
    & $mutate $copy
    $rejected = $false
    try { Assert-SameRuntimeManifest $original $copy } catch { $rejected = $true }
    if (-not $rejected) { throw 'Manifest identity accepted a mismatch/invalid descriptor.' }
}
Write-Host 'PASS: runtime manifest equality and seven negative identity cases.'

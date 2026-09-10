# Explicit download only. The candidate never installs into the host or production.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$directory = Join-Path $root 'build/transport-review'
$wheel = Join-Path $directory 'curl_cffi-0.16.3-cp310-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl'
$expected = 'a875a661e2f9a949be29454880bbb9553307a487c4c08819738298cf5c1622e2'
if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory | Out-Null }
if (-not (Test-Path -LiteralPath $wheel)) {
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri 'https://files.pythonhosted.org/packages/72/01/2bbf141baa0fc3921d31a90de5465b7a94188845a8fe84dee86bf7bd90f1/curl_cffi-0.16.3-cp310-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl' -OutFile $wheel
}
if ((Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'Candidate wheel hash mismatch; refusing use or automatic replacement.'
}
Write-Host 'PASS: official 0.16.3 wheel cached and SHA256 verified; not installed.'

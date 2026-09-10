$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$directory = Join-Path $root 'build/ddg-web-review'
$source = Join-Path $directory 'duckduckgo_web.py'
if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory | Out-Null }
if (-not (Test-Path -LiteralPath $source)) {
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri 'https://raw.githubusercontent.com/searxng/searxng/765a9999dfde789c3b194c2474f86f3212675c36/searx/engines/duckduckgo_web.py' -OutFile $source
}
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'e3cf8fe33807c62d504a2b39e790e38ce6353850a367816fbdcce6c441ee7f73') {
    throw 'Upstream source hash mismatch; refusing use or automatic replacement.'
}
Write-Host 'PASS: frozen official DDG web source cached and verified; not installed.'

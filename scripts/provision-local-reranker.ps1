param([switch]$Build)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$target = Join-Path $root 'data/models/bge-reranker-v2-m3'
$revision = '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e'
$files = @{
    'model.safetensors' = 'd9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286'
    'tokenizer.json' = '69564b696052886ed0ac63fa393e928384e0f8caada38c1f4864a9bfbf379c15'
    'sentencepiece.bpe.model' = 'cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865'
    'config.json' = '9f62673cb00ec41dcec8947b9ed16f6f2eb23ba2'
    'tokenizer_config.json' = '328a00a9a560aadcf2a3064f917517359eb3cc26'
    'special_tokens_map.json' = 'b1879d702821e753ffe4245048eee415d54a9385'
    'README.md' = '553540879ec61aea21df00434c984c0f760a3fcc'
}
function Test-Artifact([string]$Path, [string]$Expected) {
    if ($Expected.Length -eq 64) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $Expected }
    $bytes = [IO.File]::ReadAllBytes($Path)
    $header = [Text.Encoding]::ASCII.GetBytes("blob $($bytes.Length)`0")
    $algorithm = [Security.Cryptography.SHA1]::Create()
    try { $actual = [BitConverter]::ToString($algorithm.ComputeHash([byte[]]($header + $bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
    return $actual -eq $Expected
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
foreach ($name in ($files.Keys | Sort-Object)) {
    $destination = Join-Path $target $name
    if (Test-Path -LiteralPath $destination) {
        if (-not (Test-Artifact $destination $files[$name])) { throw "Existing artifact mismatch: $name; refusing overwrite." }
        Write-Host "Verified existing $name"
        continue
    }
    $partial = "$destination.part"
    if (Test-Path -LiteralPath $partial) { throw "Partial download exists for $name; inspect before retry." }
    & curl.exe --fail --location --silent --show-error --proto '=https' --proto-redir '=https' --max-time 1800 --output $partial "https://huggingface.co/BAAI/bge-reranker-v2-m3/resolve/$revision/$name"
    if ($LASTEXITCODE -ne 0) { throw "Provisioning failed for $name" }
    if (-not (Test-Artifact $partial $files[$name])) { throw "Downloaded artifact mismatch: $name" }
    Move-Item -LiteralPath $partial -Destination $destination
    Write-Host "Provisioned and verified $name"
}
if ($Build) {
    & docker build -t anonexplo/reranker-trial:cpu-v1 (Join-Path $root 'images/reranker-trial')
    if ($LASTEXITCODE -ne 0) { throw 'Reranker runtime build failed.' }
}

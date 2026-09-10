param([switch]$Live, [switch]$Integration, [ValidateSet('anonexplo/searxng:date-merge-v1','anonexplo/searxng:validation')][string]$Image='anonexplo/searxng:date-merge-v1')
$ErrorActionPreference = 'Stop'
if ($Live) { throw 'This web candidate is offline-only; no live trial implemented or authorized.' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $root 'build/ddg-web-review/duckduckgo_web.py'
if (-not (Test-Path -LiteralPath $source)) { throw 'Run provision-ddg-web-review.ps1 explicitly first.' }
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'e3cf8fe33807c62d504a2b39e790e38ce6353850a367816fbdcce6c441ee7f73') { throw 'Upstream source hash mismatch.' }
$runner = if ($Integration) { '/diagnostic/test_ddg_web_integration.py' } else { '/diagnostic/test_ddg_web_native.py' }
docker run --rm --pull never --network none --read-only --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges:true --log-driver none --memory 768m --cpus 1 --pids-limit 128 `
    --tmpfs /tmp:rw,noexec,nosuid,size=64m,mode=1777 `
    --env PYTHONDONTWRITEBYTECODE=1 --env PYTHONPATH=/usr/local/searxng `
    --mount "type=bind,source=$PSScriptRoot,target=/diagnostic,readonly" `
    --mount "type=bind,source=$source,target=/upstream/duckduckgo_web.py,readonly" `
    --entrypoint /usr/local/searxng/.venv/bin/python $Image $runner
if ($LASTEXITCODE -ne 0) { throw 'Offline web candidate checks failed; no provider queries sent.' }

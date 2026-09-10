$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$model = Join-Path $root 'data/models/bge-reranker-v2-m3'
if (-not (Test-Path -LiteralPath (Join-Path $model 'model.safetensors'))) { throw 'Provision the model explicitly first.' }
if ((Get-FileHash -LiteralPath (Join-Path $model 'model.safetensors') -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286') { throw 'Model hash mismatch' }
& docker run --rm --pull never --network none --read-only --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges:true --log-driver none --memory 12g --cpus 8 --pids-limit 256 --tmpfs /tmp:rw,noexec,nosuid,size=256m,mode=1777 --mount "type=bind,source=$model,target=/model,readonly" --mount "type=bind,source=$PSScriptRoot,target=/trial,readonly" anonexplo/reranker-trial:cpu-v1 /trial/run-reranker-trial.py
if ($LASTEXITCODE -ne 0) { throw 'Offline reranker test failed.' }

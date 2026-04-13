$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

function Get-EnvValue {
    param(
        [string]$Key,
        [string]$DefaultValue = ""
    )

    foreach ($path in @((Join-Path $root ".env"), (Join-Path $root ".env.example"))) {
        if (-not (Test-Path $path)) {
            continue
        }

        $match = Get-Content -LiteralPath $path | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))=(.*)$" } | Select-Object -First 1
        if ($match) {
            $value = ($match -replace "^\s*$([regex]::Escape($Key))=", "").Trim()
            if ($value -and -not $value.StartsWith("replace-with-")) {
                return $value
            }
        }
    }

    return $DefaultValue
}

try {
    $modelFileName = Get-EnvValue -Key "MODEL_FILE_NAME" -DefaultValue "Qwen2.5-7B-Instruct.Q4_K_M.gguf"
    $modelSourceUrl = Get-EnvValue -Key "MODEL_SOURCE_URL"
    $expectedSha = (Get-EnvValue -Key "MODEL_FILE_SHA256").ToLowerInvariant()
    $targetDirectory = Join-Path $root "data\models"
    $targetPath = Join-Path $targetDirectory $modelFileName

    if (-not $modelSourceUrl) {
        throw "MODEL_SOURCE_URL is not configured in .env or .env.example."
    }

    New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null

    if (-not (Test-Path -LiteralPath $targetPath)) {
        Write-Host "Downloading $modelFileName to data\models..."
        curl.exe -L --fail --retry 3 --continue-at - --output "$targetPath" "$modelSourceUrl"
        if ($LASTEXITCODE -ne 0) {
            throw "Model download failed."
        }
    } else {
        Write-Host "Model file already present: $targetPath"
    }

    $actualSha = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "SHA256: $actualSha"

    if ($expectedSha) {
        if ($actualSha -ne $expectedSha) {
            throw "Downloaded model checksum does not match MODEL_FILE_SHA256."
        }
        Write-Host "Checksum verified against MODEL_FILE_SHA256."
    } else {
        Write-Host "MODEL_FILE_SHA256 is empty; checksum computed but not enforced."
    }

    Write-Host "Next steps:"
    Write-Host "  1. Review .env to confirm MODEL_NAME and runtime settings"
    Write-Host "  2. Start the model runtime with docker compose --profile llamacpp up -d model-backend"
    Write-Host "  3. Run powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime"
} finally {
    Pop-Location
}

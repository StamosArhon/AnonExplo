# One-time, project-scoped migration. Does not delete images, volumes, browser
# data, .env, credentials or model files. Re-running is safe.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    $argsCompose = @('-f','docker-compose.yml','-f','docker-compose.proton-search.yml','--profile','proton-search')
    $raw = & docker compose @argsCompose config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Compose config failed.' }
    $config = $raw | ConvertFrom-Json
    . (Join-Path $PSScriptRoot 'compose-policy.ps1')
    Assert-SearchComposePolicy $config ([string]$config.services.'host-gateway'.ports[0].published) -Vpn
    & (Join-Path $PSScriptRoot 'start-proton-search.ps1')
    # Resolve exact container IDs by both project and service labels. Never
    # remove arbitrary orphans belonging to another project or unknown service.
    foreach ($service in @('ui','backend','fetcher','model-backend')) {
        $ids = @(& docker ps -aq --filter "label=com.docker.compose.project=$($config.name)" --filter "label=com.docker.compose.service=$service")
        if ($LASTEXITCODE -ne 0) { throw 'Container inventory failed.' }
        foreach ($id in $ids) {
            & docker rm -f $id
            if ($LASTEXITCODE -ne 0) { throw "Could not retire $service." }
        }
    }
    $helperDir = Join-Path $env:LOCALAPPDATA 'AnonExplo\search-fallback'
    $legacyScript = Join-Path $helperDir 'search-fallback.js'
    $legacyLauncher = Join-Path $helperDir 'start-search-fallback.vbs'
    $taskName = 'AnonExplo Search Fallback Redirector'
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        $actions = ($task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' | '
        if ($actions -notmatch [regex]::Escape($legacyLauncher)) {
            throw 'Legacy task action is unexpected; refusing to modify it.'
        }
        try {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
            Write-Host 'Removed legacy redirector scheduled task.'
        } catch {
            # Some existing tasks are admin-owned. Retire the exact user-owned
            # launcher instead, preserving a recoverable copy and reporting it.
            if (-not (Test-Path -LiteralPath $legacyLauncher -PathType Leaf)) { throw }
            $backup = "$legacyLauncher.retired-backup"
            if (-not (Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $legacyLauncher -Destination $backup }
            Set-Content -LiteralPath $legacyLauncher -Encoding ASCII -Value "' AnonExplo legacy redirector retired. No process is started."
            Write-Warning 'Task deletion denied by Windows permissions. Its launcher is now a no-op; the task entry remains.'
        }
    }
    $folder = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
    if ($folder) {
        $entry = Join-Path $folder 'AnonExplo Search Fallback Redirector.vbs'
        if (Test-Path -LiteralPath $entry -PathType Leaf) {
            $content = Get-Content -LiteralPath $entry -Raw
            if ($content -notmatch [regex]::Escape($legacyScript)) { throw 'Unexpected Startup redirector content.' }
            $backup = Join-Path $helperDir 'startup-redirector.retired-backup'
            Copy-Item -LiteralPath $entry -Destination $backup -Force
            Remove-Item -LiteralPath $entry
            Write-Host 'Retired Startup-folder redirector (backup kept).'
        }
    }
    $pattern = '(?:"' + [regex]::Escape($legacyScript) + '"|' + [regex]::Escape($legacyScript) + ')(?:\s|$)'
    foreach ($process in @(Get-CimInstance Win32_Process -Filter "name='node.exe'" | Where-Object { $_.CommandLine -match $pattern })) {
        Stop-Process -Id $process.ProcessId -ErrorAction Stop
        Write-Host 'Stopped the exact legacy redirector process.'
    }
    # Only the old, now-unused model network; never disconnect active endpoints.
    $networkName = "$($config.name)_model_internal"
    $networks = @(& docker network ls --filter "label=com.docker.compose.project=$($config.name)" --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) { throw 'Network inventory failed.' }
    if ($networkName -in $networks) {
        $network = (& docker network inspect $networkName | ConvertFrom-Json)[0]
        if (@($network.Containers.PSObject.Properties).Count -eq 0) {
            & docker network rm $networkName
            if ($LASTEXITCODE -ne 0) { throw 'Unused model network removal failed.' }
        }
    }
    Write-Host 'Legacy runtime components retired. Data, browser profiles, credentials and cached images preserved.'
} finally { Pop-Location }

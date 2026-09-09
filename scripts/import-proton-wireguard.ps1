param([string]$ConfigPath, [switch]$BrowserImport, [int]$Port = 18765)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$destination = Join-Path $root 'data\proton\wireguard\wg0.conf'

function Save-ProtonKey([string]$ConfigText) {
    $keys = [regex]::Matches($ConfigText, '(?m)^PrivateKey\s*=\s*([A-Za-z0-9+/]{43}=)\s*$')
    if ($keys.Count -ne 1 -or [Convert]::FromBase64String($keys[0].Groups[1].Value).Length -ne 32) {
        throw 'Expected one valid WireGuard private key; nothing imported.'
    }
    if (Test-Path -LiteralPath $destination) { throw 'A local key already exists; refusing to overwrite it.' }
    $directory = Split-Path $destination
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value, 'S-1-5-18', 'S-1-5-32-544')) {
        $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $directory -AclObject $acl
    # Retain only the client key/address: Gluetun selects a current paid server
    # using PROTON_SERVER_COUNTRIES, without an aging downloaded server endpoint.
    $text = "[Interface]`nPrivateKey = $($keys[0].Groups[1].Value)`nAddress = 10.2.0.2/32`n"
    $stream = [IO.File]::Open($destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    try { $bytes = [Text.Encoding]::UTF8.GetBytes($text); $stream.Write($bytes, 0, $bytes.Length) }
    finally { $stream.Dispose(); $text = $null; $bytes = $null }
}

if ($ConfigPath) {
    Save-ProtonKey (Get-Content -LiteralPath $ConfigPath -Raw)
    Write-Host 'Imported the Proton key into the restricted, Git-ignored local credential file.'
    return
}
if (-not $BrowserImport) { throw 'Supply -ConfigPath or explicitly select -BrowserImport.' }
if (Test-Path -LiteralPath $destination) { throw 'A local key already exists; refusing to overwrite it.' }
$nonce = [Guid]::NewGuid().ToString('N')
$origin = "http://127.0.0.1:$Port"
$path = "/$nonce/"
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("$origin/")
$listener.Start()
Write-Host "One-use local import: $origin$path"
Write-Host 'No request logging. The listener expires in 10 minutes or after one successful import.'
$deadline = [DateTime]::UtcNow.AddMinutes(10)
try {
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = $listener.GetContextAsync()
        while (-not $pending.Wait(500)) {
            if ([DateTime]::UtcNow -ge $deadline) { throw 'Local import expired.' }
        }
        $context = $pending.Result
        $request = $context.Request
        $response = $context.Response
        $response.Headers.Add('Cache-Control', 'no-store')
        $response.Headers.Add('Referrer-Policy', 'same-origin')
        $response.Headers.Add('Content-Security-Policy', "default-src 'none'; form-action 'self'; frame-ancestors 'none'")
        $response.ContentType = 'text/html; charset=utf-8'
        $complete = $false
        if ($request.Url.AbsolutePath -ne $path -or $request.Headers['Host'] -ne "127.0.0.1:$Port") {
            $response.StatusCode = 404; $body = 'Not found'
        } elseif ($request.HttpMethod -eq 'GET') {
            $body = '<!doctype html><title>AnonExplo local VPN import</title><h1>Import Proton WireGuard configuration</h1><p>Only the key and client address are saved locally. Nothing is uploaded externally.</p><form method="post" autocomplete="off"><label>WireGuard configuration<textarea name="config" autocomplete="off" rows="16" cols="75"></textarea></label><button>Import locally</button></form>'
        } elseif ($request.HttpMethod -eq 'POST' -and $request.Headers['Origin'] -eq $origin -and $request.ContentLength64 -gt 0 -and $request.ContentLength64 -le 8192 -and $request.ContentType -like 'application/x-www-form-urlencoded*') {
            try {
                $reader = New-Object IO.StreamReader($request.InputStream)
                try { $form = $reader.ReadToEnd() } finally { $reader.Dispose() }
                if (-not $form.StartsWith('config=') -or $form.Contains('&')) { throw 'Invalid form' }
                Save-ProtonKey ([Uri]::UnescapeDataString($form.Substring(7).Replace('+', ' ')))
                $form = $null
                $body = '<!doctype html><title>Import complete</title><h1>Import complete</h1><p>The key is stored locally, excluded from Git, and has not been printed.</p>'
                $complete = $true
            } catch { $response.StatusCode = 400; $body = 'Import failed. Check format and whether a credential already exists.' }
        } else {
            $response.StatusCode = 403; $body = 'Request rejected'
        }
        $payload = [Text.Encoding]::UTF8.GetBytes($body)
        $response.ContentLength64 = $payload.Length
        $response.OutputStream.Write($payload, 0, $payload.Length)
        $response.Close()
        if ($complete) { Write-Host 'Proton key imported successfully; local listener stopped.'; break }
    }
} finally { $listener.Stop(); $listener.Close() }

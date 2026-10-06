param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$studioRoot = $PSScriptRoot
$studioUrl = 'http://127.0.0.1:8195'
$studioPython = Join-Path $studioRoot '..\Plenio-Portable\ComfyUI_windows_portable\python_embeded\python.exe'
$studioConfig = Join-Path $studioRoot 'config.json'
if (Test-Path -LiteralPath $studioConfig) {
    $settings = Get-Content -LiteralPath $studioConfig -Raw | ConvertFrom-Json
    if ($settings.python) {
        $studioPython = $settings.python
        if (-not [IO.Path]::IsPathRooted($studioPython)) { $studioPython = Join-Path $studioRoot $studioPython }
    }
    if ($settings.portable) {
        . (Join-Path $studioRoot 'scripts\Portable-Common.ps1')
        Set-PortableEnvironment $studioRoot
        & (Join-Path $studioRoot 'scripts\Start-Engine.ps1')
    }
}
if (-not (Test-Path -LiteralPath $studioPython)) { throw 'Run Setup-GimmeMusic.ps1 with your ComfyUI path and its Python executable first.' }
if (-not (Test-Path -LiteralPath (Join-Path $studioRoot 'dist\index.html'))) { throw 'Frontend is not built. Run npm ci and npm run build, or run Setup-GimmeMusic.ps1.' }
$existing = $null
try { $existing = Invoke-RestMethod "$studioUrl/api/status" -TimeoutSec 3 } catch {}
if ($existing -and $existing.app -ne 'GimmeMusic') { throw 'Port 8195 is occupied by a different app.' }
if ($existing -and $settings -and $settings.portable) {
    $owned = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains((Join-Path $studioRoot 'server.py')) }
    if (-not $owned) { throw 'Another GimmeMusic folder is running on port 8195. Stop it before starting this portable copy.' }
}
if (-not $existing) {
    $null = New-Item -ItemType Directory -Path (Join-Path $studioRoot 'data') -Force
    $studioProcess = Start-Process -FilePath $studioPython -ArgumentList ('"' + (Join-Path $studioRoot 'server.py') + '"') -WorkingDirectory $studioRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $studioRoot 'data\server.stdout.log') -RedirectStandardError (Join-Path $studioRoot 'data\server.stderr.log')
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try { $existing = Invoke-RestMethod "$studioUrl/api/status" -TimeoutSec 2; break } catch { Start-Sleep -Milliseconds 500 }
        if ($studioProcess.HasExited) { throw 'Studio startup failed. See data\server.stderr.log.' }
    }
    if (-not $existing -or $existing.app -ne 'GimmeMusic') { throw 'Studio did not become ready. See data\server.stderr.log.' }
}
if (-not $NoBrowser) { Start-Process $studioUrl }

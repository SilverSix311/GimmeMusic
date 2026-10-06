$ErrorActionPreference = 'Stop'
$appRoot = Split-Path $PSScriptRoot -Parent
$engineRoot = Join-Path $appRoot 'runtime\ComfyUI_windows_portable'
$enginePython = Join-Path $engineRoot 'python_embeded\python.exe'
$engineScript = Join-Path $engineRoot 'ComfyUI\main.py'
$engineUrl = 'http://127.0.0.1:8189'
$existingEngine = $null
try { $existingEngine = Invoke-RestMethod "$engineUrl/system_stats" -TimeoutSec 2 } catch {}
$ownedEngine = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.ExecutablePath -eq $enginePython -and $_.CommandLine -and $_.CommandLine.Contains($engineScript) }
if ($existingEngine) {
    if (-not $ownedEngine) { throw 'Another ComfyUI installation is using port 8189. Stop it before starting this portable copy.' }
    return
}
$logRoot = Join-Path $appRoot 'runtime\logs'
$null = New-Item -ItemType Directory -Force -Path $logRoot
$enginePid = $ownedEngine.ProcessId
if (-not $ownedEngine) {
    $ownedEngine = Start-Process -FilePath $enginePython -ArgumentList @('-s', ('"' + $engineScript + '"'), '--windows-standalone-build', '--listen', '127.0.0.1', '--port', '8189') -WorkingDirectory $engineRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'comfy.stdout.log') -RedirectStandardError (Join-Path $logRoot 'comfy.stderr.log')
    $enginePid = $ownedEngine.Id
}
Write-Host 'Starting the music engine...'
for ($attempt = 0; $attempt -lt 180; $attempt++) {
    try { $null = Invoke-RestMethod "$engineUrl/system_stats" -TimeoutSec 2; return } catch {}
    if (-not (Get-Process -Id $enginePid -ErrorAction SilentlyContinue)) { throw "Engine startup failed. See $logRoot\comfy.stderr.log" }
    Start-Sleep -Seconds 1
}
throw "Engine startup timed out. See $logRoot\comfy.stderr.log"

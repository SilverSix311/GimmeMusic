$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Stop-GimmeMusic.ps1')
$enginePython = Join-Path $PSScriptRoot 'runtime\ComfyUI_windows_portable\python_embeded\python.exe'
$engineScript = Join-Path $PSScriptRoot 'runtime\ComfyUI_windows_portable\ComfyUI\main.py'
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.ExecutablePath -eq $enginePython -and $_.CommandLine -and $_.CommandLine.Contains($engineScript)
} | ForEach-Object { Stop-Process -Id $_.ProcessId }
Write-Host 'This portable engine stopped. Other installations were left running.'

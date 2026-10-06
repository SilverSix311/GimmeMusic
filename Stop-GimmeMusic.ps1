$studioServer = Join-Path $PSScriptRoot 'server.py'
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains($studioServer)
} | ForEach-Object { Stop-Process -Id $_.ProcessId }
Write-Host 'GimmeMusic stopped. ComfyUI remains running.'

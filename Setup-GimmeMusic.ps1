param(
    [Parameter(Mandatory=$true)][string]$ComfyRoot,
    [Parameter(Mandatory=$true)][string]$Python,
    [string]$EngineUrl = 'http://127.0.0.1:8189',
    [switch]$SkipDependencies,
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$setupArgs = @((Join-Path $PSScriptRoot 'scripts\setup.py'), '--comfy-root', $ComfyRoot, '--engine-url', $EngineUrl)
if ($SkipDependencies) { $setupArgs += '--skip-dependencies' }
& $Python @setupArgs
if ($LASTEXITCODE -ne 0) { throw 'Setup failed; see the error above.' }
if (-not $SkipBuild) {
    Push-Location $PSScriptRoot
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed. Install Node.js 20.19+ or 22.12+ first.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host 'Setup complete. Start ComfyUI, then run Start-GimmeMusic.bat.'

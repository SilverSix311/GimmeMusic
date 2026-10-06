param([switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$portableRoot = $PSScriptRoot
. (Join-Path $portableRoot 'scripts\Portable-Common.ps1')
if (-not [Environment]::Is64BitOperatingSystem) { throw 'GimmeMusic Portable requires 64-bit Windows and an NVIDIA GPU.' }
if (-not (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue)) { throw 'Install the NVIDIA graphics driver first, then rerun this installer.' }
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) { throw 'Windows curl.exe is required. Update Windows, then rerun.' }
$runtime = Join-Path $portableRoot 'runtime'
$statePath = Join-Path $runtime 'install-state.json'
$engineRoot = Join-Path $runtime 'ComfyUI_windows_portable'
$comfyRoot = Join-Path $engineRoot 'ComfyUI'
$portablePython = Join-Path $engineRoot 'python_embeded\python.exe'
if ((Test-Path -LiteralPath $engineRoot) -and -not (Test-Path -LiteralPath $statePath)) {
    throw 'runtime\ComfyUI_windows_portable already exists without an installer record. Use an empty portable folder; existing installations are not overwritten.'
}
$state = @{}
if (Test-Path -LiteralPath $statePath) {
    (Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $state[$_.Name] = $_.Value }
}
function Save-Step([string]$Name) {
    $state[$Name] = $true
    $state | ConvertTo-Json | Set-Content -LiteralPath "$statePath.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$statePath.tmp" -Destination $statePath -Force
}
Set-PortableEnvironment $portableRoot
$packages = Get-Content (Join-Path $portableRoot 'workflows\portable.json') -Raw | ConvertFrom-Json
$upstream = Get-Content (Join-Path $portableRoot 'workflows\upstream.json') -Raw | ConvertFrom-Json
$downloads = Join-Path $runtime 'downloads'
Write-Host 'GimmeMusic Portable - Windows / NVIDIA' -ForegroundColor Magenta
Write-Host 'Installs ComfyUI, Plenio, the studio, workflows, and 17.2 GiB of models inside this folder.'
Write-Host 'Downloads resume if interrupted. No administrator access or system Python/Node/Git is needed.'
$drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($portableRoot).TrimEnd('\').TrimEnd(':')) -ErrorAction SilentlyContinue
if (-not $state.models -and $drive -and $drive.Free -lt 40GB) { throw 'At least 40 GiB free disk space is needed for the initial portable install.' }
Save-Step 'started'
$extractor = Get-PortablePackage $packages.extractor $downloads
if (-not $state.git) {
    $archive = Get-PortablePackage $packages.git $downloads
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $runtime 'git') -Force
    Save-Step 'git'
}
if (-not $state.comfy) {
    $archive = Get-PortablePackage $packages.comfy $downloads
    Invoke-Checked $extractor @('x', $archive, "-o$runtime", '-y')
    Invoke-Checked 'git.exe' @('-C', $comfyRoot, 'fetch', 'origin', $upstream.tested_comfyui_commit)
    Invoke-Checked 'git.exe' @('-C', $comfyRoot, 'checkout', '--detach', $upstream.tested_comfyui_commit)
    Save-Step 'comfy'
}
if (-not $state.dependencies) {
    Invoke-Checked $portablePython @('-m', 'pip', 'install', '-r', (Join-Path $comfyRoot 'requirements.txt'), '-r', (Join-Path $portableRoot 'requirements.txt'), 'faster-whisper==1.2.1', 'ctranslate2==4.8.2', 'rotary-embedding-torch==0.9.1', 'nvidia-cublas-cu12==12.9.2.10')
    Save-Step 'dependencies'
}
Invoke-Checked $portablePython @((Join-Path $portableRoot 'scripts\setup.py'), '--comfy-root', $comfyRoot, '--skip-dependencies', '--portable')
Invoke-Checked $portablePython @((Join-Path $portableRoot 'scripts\verify_portable.py'), '--comfy-root', $comfyRoot, '--runtime-only')
if (-not (Test-Path -LiteralPath (Join-Path $portableRoot 'dist\index.html'))) {
    $nodeZip = Get-PortablePackage $packages.node $downloads
    Expand-Archive -LiteralPath $nodeZip -DestinationPath $runtime -Force
    $nodeRoot = Join-Path $runtime $packages.node.directory
    $env:PATH = "$nodeRoot;" + $env:PATH
    Push-Location $portableRoot
    try {
        Invoke-Checked (Join-Path $nodeRoot 'npm.cmd') @('ci')
        Invoke-Checked (Join-Path $nodeRoot 'npm.cmd') @('run', 'build')
    } finally { Pop-Location }
}
Invoke-Checked $portablePython @((Join-Path $portableRoot 'scripts\download_models.py'), '--comfy-root', $comfyRoot)
Save-Step 'models'
Invoke-Checked $portablePython @((Join-Path $portableRoot 'scripts\verify_portable.py'), '--comfy-root', $comfyRoot)
Save-Step 'verified'
Write-Host 'Ready! Double-click Start-GimmeMusic.bat to start both ComfyUI and the studio.' -ForegroundColor Green
Write-Host 'You can move this entire folder. Keep runtime, data and the application together.'
if (-not $NoLaunch) { & (Join-Path $portableRoot 'Start-GimmeMusic.ps1') }

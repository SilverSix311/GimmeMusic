function Set-PortableEnvironment([string]$Root) {
    $env:HF_HOME = Join-Path $Root 'runtime\cache\huggingface'
    $env:TORCH_HOME = Join-Path $Root 'runtime\cache\torch'
    $env:XDG_CACHE_HOME = Join-Path $Root 'runtime\cache'
    $env:PIP_CACHE_DIR = Join-Path $Root 'runtime\cache\pip'
    $env:npm_config_cache = Join-Path $Root 'runtime\cache\npm'
    $env:TEMP = Join-Path $Root 'runtime\temp'
    $env:TMP = $env:TEMP
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    $env:DO_NOT_TRACK = '1'
    $env:PYTHONNOUSERSITE = '1'
    $env:PATH = (Join-Path $Root 'runtime\git\cmd') + ';' + $env:PATH
    $null = New-Item -ItemType Directory -Force -Path $env:TEMP, $env:XDG_CACHE_HOME
}

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed (exit $LASTEXITCODE). Fix the error above and rerun the installer." }
}

function Get-PortablePackage($Package, [string]$Directory) {
    $null = New-Item -ItemType Directory -Force -Path $Directory
    $target = Join-Path $Directory $Package.file
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -eq $Package.sha256) { return $target }
        throw "Cached package checksum differs: $target. Remove that file and rerun."
    }
    $part = "$target.part"
    if ((Test-Path -LiteralPath $part) -and (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash -eq $Package.sha256) {
        Move-Item -LiteralPath $part -Destination $target
        return $target
    }
    Write-Host "Downloading $($Package.file) (resumable)..." -ForegroundColor Cyan
    Invoke-Checked 'curl.exe' @('-L', '--fail', '--retry', '4', '--retry-delay', '3', '-C', '-', '-o', $part, $Package.url)
    if ((Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash -ne $Package.sha256) {
        Remove-Item -LiteralPath $part
        throw "Checksum failed for $($Package.file). Rerun to download a fresh copy."
    }
    Move-Item -LiteralPath $part -Destination $target
    return $target
}

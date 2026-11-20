<#
.SYNOPSIS
    Install Chatterbox TTS (voice cloning) into an isolated tools venv.

.DESCRIPTION
    Creates tools/chatterbox/.venv, installs PyTorch and chatterbox-tts, and
    keeps all caches and model weights on D:. The main backend venv is never
    modified. Use -Cpu to install the CPU build instead of CUDA 12.4.

.EXAMPLE
    .\scripts\install_chatterbox.ps1
    .\scripts\install_chatterbox.ps1 -Cpu
#>
param([switch]$Cpu)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "tools\chatterbox"
$venv = Join-Path $tools ".venv"
$python = Join-Path $venv "Scripts\python.exe"

$env:PIP_CACHE_DIR = Join-Path $root "tools\pip-cache"
$env:TMP = Join-Path $root "tools\tmp"
$env:TEMP = $env:TMP
$env:HF_HOME = Join-Path $root "models\huggingface"
New-Item -ItemType Directory -Force $tools, $env:PIP_CACHE_DIR, $env:TMP, $env:HF_HOME | Out-Null

if (-not (Test-Path $python)) {
    $base = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $base) { throw "Python 3.10+ was not found on PATH." }
    Write-Host "Creating $venv" -ForegroundColor Cyan
    & $base -m venv $venv
}

Write-Host "Upgrading pip" -ForegroundColor Cyan
& $python -m pip install --upgrade pip

Write-Host "Installing PyTorch" -ForegroundColor Cyan
if ($Cpu) {
    & $python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
} else {
    & $python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
}

Write-Host "Installing chatterbox-tts 0.1.7 (MIT)" -ForegroundColor Cyan
& $python -m pip install chatterbox-tts==0.1.7

Write-Host ""
Write-Host "Installed. Add reference clips to:" -ForegroundColor Green
Write-Host "  $tools\voices" -ForegroundColor Green
Write-Host "Then restart the backend and select 'Chatterbox (voice cloning)' in Voice & Dialogue." -ForegroundColor Green

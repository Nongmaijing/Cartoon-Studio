# Starts the Cartoon Studio FastAPI backend on http://127.0.0.1:8010
param([switch]$Reload)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Python virtual environment not found." -ForegroundColor Red
    Write-Host "Run this once to create it:"
    Write-Host "  cd `"$backend`""
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Write-Host "Cartoon Studio backend -> http://127.0.0.1:8010" -ForegroundColor Cyan
Write-Host "API docs                -> http://127.0.0.1:8010/docs" -ForegroundColor DarkGray

Push-Location $backend
try {
    if ($Reload) {
        & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
    } else {
        & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
    }
} finally {
    Pop-Location
}

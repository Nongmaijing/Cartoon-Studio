# Starts the Cartoon Studio Vite dev server on http://127.0.0.1:5173
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Frontend dependencies are not installed." -ForegroundColor Red
    Write-Host "Run this once:"
    Write-Host "  cd `"$frontend`""
    Write-Host "  npm install"
    exit 1
}

Write-Host "Cartoon Studio frontend -> http://127.0.0.1:5173" -ForegroundColor Cyan
Push-Location $frontend
try {
    npm run dev
} finally {
    Pop-Location
}

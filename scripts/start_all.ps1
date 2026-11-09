# Starts Cartoon Studio backend and frontend in separate PowerShell windows.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$backendScript = Join-Path $root "scripts\start_backend.ps1"
$frontendScript = Join-Path $root "scripts\start_frontend.ps1"

Write-Host "Starting Cartoon Studio..." -ForegroundColor Cyan
Write-Host "  Backend : http://127.0.0.1:8010"
Write-Host "  Frontend: http://127.0.0.1:5173"
Write-Host ""
Write-Host "Close the two server windows (or run scripts\stop_all.ps1) to stop." -ForegroundColor DarkGray

Start-Process powershell -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$backendScript`""
) -WorkingDirectory $root

Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$frontendScript`""
) -WorkingDirectory $root

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"

# Starts the OpenCode bridge MCP server on port 8030.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Backend virtual environment not found at $python"
}

Write-Host "Starting OpenCode bridge MCP server..." -ForegroundColor Cyan
Write-Host "  MCP endpoint: http://127.0.0.1:8030/mcp"
Write-Host "  Health      : http://127.0.0.1:8030/health"
Write-Host "  Auth        : Bearer token with scope 'opencode'"
Write-Host ""

Push-Location $backend
try {
    & $python run_mcp.py --transport streamable-http --profile opencode --host 127.0.0.1 --port 8030 --public-url http://127.0.0.1:8030
} finally {
    Pop-Location
}

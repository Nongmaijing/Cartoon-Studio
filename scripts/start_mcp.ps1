# Starts the Cartoon Studio MCP server on port 8020.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Backend virtual environment not found at $python"
}

Write-Host "Starting Cartoon Studio MCP server..." -ForegroundColor Cyan
Write-Host "  MCP endpoint: http://127.0.0.1:8020/mcp"
Write-Host "  Health      : http://127.0.0.1:8020/health"
Write-Host "  Auth        : Bearer token (MCP_BEARER_TOKEN or /api/v1/mcp/tokens)"
Write-Host ""

Push-Location $backend
try {
    & $python run_mcp.py --transport streamable-http --host 127.0.0.1 --port 8020
} finally {
    Pop-Location
}

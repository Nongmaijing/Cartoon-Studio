# Stops only the processes listening on Cartoon Studio's ports (8010, 5173 and 8020).
$ErrorActionPreference = "SilentlyContinue"

foreach ($port in 8010, 5173, 8020) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "Port $port is not in use."
        continue
    }
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $pids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Stopping $($proc.ProcessName) (PID $processId) on port $port..."
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Cartoon Studio stopped." -ForegroundColor Cyan

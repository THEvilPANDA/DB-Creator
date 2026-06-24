# Stop all DB Creator processes (Windows)
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "Stopping DB Creator..."

# Kill processes on backend + frontend ports
@(8000, 5173) | ForEach-Object {
    $port = $_
    $lines = netstat -ano 2>$null | Select-String ":$port\s"
    $lines | ForEach-Object {
        if ($_ -match "\s+(\d+)$") {
            $pid = [int]$Matches[1]
            try {
                Stop-Process -Id $pid -Force -ErrorAction Stop
                Write-Host "  Killed PID $pid (port $port)"
            } catch {}
        }
    }
}

# Stop Docker services
Set-Location $Root
docker compose stop
Write-Host "  Docker services stopped"
Write-Host "Done."

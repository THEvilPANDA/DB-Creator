#Requires -Version 5.1
$Root = Split-Path $PSScriptRoot -Parent

$null = docker compose version 2>$null
if ($LASTEXITCODE -eq 0) {
    function Invoke-Compose { docker compose @args }
} elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    function Invoke-Compose { docker-compose @args }
} else {
    Write-Host "ERROR: Neither 'docker compose' nor 'docker-compose' found." -ForegroundColor Red
    exit 1
}

Write-Host "Stopping DB Creator..."
Set-Location $Root
Invoke-Compose down
Write-Host "Done."
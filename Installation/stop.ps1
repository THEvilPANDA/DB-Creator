$Root = Split-Path $PSScriptRoot -Parent
Write-Host "Stopping DB Creator..."
Set-Location $Root
docker compose down
Write-Host "Done."

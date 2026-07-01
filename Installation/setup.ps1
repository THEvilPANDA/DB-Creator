#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root            = Split-Path $PSScriptRoot -Parent
$BackendEnvFile  = Join-Path (Join-Path $Root "backend") ".env"
$FrontendEnvFile = Join-Path (Join-Path $Root "frontend") ".env"

function Write-Step  { param($msg) Write-Host "  " -NoNewline; Write-Host "OK " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Fatal { param($msg) Write-Host "`n  ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host "================================================================="
Write-Host "             DB Creator -- Setup & Start"
Write-Host "================================================================="

# 1. backend/.env
if (-not (Test-Path $BackendEnvFile)) {
    @"
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=dev-admin-key
JWT_SECRET=dev-jwt-secret-change-in-production
DEFAULT_ADMIN_PASSWORD=admin123
"@ | Set-Content $BackendEnvFile -Encoding utf8
    Write-Step "Created backend/.env"
} else {
    Write-Step "backend/.env exists"
}

# 2. frontend/.env
if (-not (Test-Path $FrontendEnvFile)) {
    "VITE_ADMIN_KEY=dev-admin-key" | Set-Content $FrontendEnvFile -Encoding utf8
    Write-Step "Created frontend/.env"
} else {
    Write-Step "frontend/.env exists"
}

# 3. Docker check
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fatal "Docker not found. Install Docker Desktop from https://www.docker.com and re-run."
}
$null = docker info 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fatal "Docker Desktop is not running. Start it from the taskbar, then re-run this script."
}
Write-Step "Docker running"

# 4. Start
Set-Location $Root
Write-Host ""
Write-Host "  Starting all services (first run builds images -- takes a few minutes)..." -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) { Write-Fatal "docker compose up failed. Check output above." }

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "  All systems go!" -ForegroundColor Green
Write-Host "-----------------------------------------------------------------" -ForegroundColor Green
Write-Host "  Frontend  ->  http://localhost:5173" -ForegroundColor Green
Write-Host "  Backend   ->  http://localhost:8000" -ForegroundColor Green
Write-Host "  API docs  ->  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "-----------------------------------------------------------------" -ForegroundColor Green
Write-Host "  Login:  admin / admin123" -ForegroundColor Green
Write-Host "-----------------------------------------------------------------" -ForegroundColor Green
Write-Host "  Logs:   docker compose logs -f" -ForegroundColor Green
Write-Host "  Stop:   .\Installation\stop.ps1" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green

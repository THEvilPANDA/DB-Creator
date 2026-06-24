# DB Creator — setup + start script (Windows / PowerShell)
# Run from project root:  .\Installation\setup.ps1
# Or from anywhere:       powershell -ExecutionPolicy Bypass -File "G:\AI\DBCreator\Installation\setup.ps1"
#Requires -Version 5.1

$ErrorActionPreference = "Stop"

# ── Paths ──────────────────────────────────────────────────────────────────────
$Root     = Split-Path $PSScriptRoot -Parent
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv     = Join-Path $Root ".venv"
$Logs     = Join-Path $Root "logs"
$EnvFile  = Join-Path $Backend ".env"
$VenvPy   = Join-Path $Venv "Scripts\python.exe"
$VenvPip  = Join-Path $Venv "Scripts\pip.exe"
$VenvAlem = Join-Path $Venv "Scripts\alembic.exe"

function Write-Step  { param($msg) Write-Host "  " -NoNewline; Write-Host "OK " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Warn  { param($msg) Write-Host "  " -NoNewline; Write-Host "!  " -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Write-Sec   { param($msg) Write-Host ""; Write-Host "── $msg " -ForegroundColor Cyan }
function Write-Fatal { param($msg) Write-Host "`n  ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host "================================================================="
Write-Host "             DB Creator -- Setup & Start"
Write-Host "================================================================="
Write-Host "  Root: $Root"

# ── 1. Prerequisites ───────────────────────────────────────────────────────────
Write-Sec "Prerequisites"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Warn "Installing Docker Desktop via winget..."
    winget install Docker.DockerDesktop --silent --accept-source-agreements --accept-package-agreements
    Write-Host "`n  Docker Desktop installed. Start it from the Start menu, then re-run this script." -ForegroundColor Yellow
    exit 0
}

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and
    -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
    Write-Warn "Installing Python 3.11 via winget..."
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    Write-Fatal "Python installed. Open a new terminal and re-run this script."
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Warn "Installing Node.js via winget..."
    winget install OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    Write-Fatal "Node.js installed. Open a new terminal and re-run this script."
}

# Resolve python: prefer python3 but skip the Windows Store stub (exit code 9009)
$PyCmd = "python"
try {
    $ver = & python3 --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $ver -match "Python \d") { $PyCmd = "python3" }
} catch {}
if ($PyCmd -eq "python" -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Fatal "Python not found. Install from https://python.org or via winget."
}

Write-Step "docker  $(docker --version)"
Write-Step "python  $(& $PyCmd --version 2>&1)"
Write-Step "node    $(node --version)"

# ── 2. .env ───────────────────────────────────────────────────────────────────
Write-Sec ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Warn "Creating backend/.env with dev defaults..."
    @"
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
TEST_DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator_test
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=dev-admin-key
JWT_SECRET=dev-jwt-secret-change-in-production
DEFAULT_ADMIN_PASSWORD=admin123
"@ | Set-Content $EnvFile -Encoding utf8
    Write-Step "Created (edit before production use)"
} else {
    Write-Step ".env already exists"
}

# ── 3. Docker services ────────────────────────────────────────────────────────
Write-Sec "Docker services"

$dockerRunning = $false
try { docker info 2>&1 | Out-Null; $dockerRunning = $? } catch {}

if (-not $dockerRunning) {
    Write-Warn "Starting Docker Desktop..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
    Write-Host "  Waiting for Docker to start" -NoNewline
    $waited = 0
    while ($waited -lt 60) {
        Start-Sleep -Seconds 3; $waited += 3
        try { docker info 2>&1 | Out-Null; if ($?) { break } } catch {}
        Write-Host "." -NoNewline
    }
    Write-Host ""
    if ($waited -ge 60) { Write-Fatal "Docker did not start. Please start Docker Desktop manually and re-run." }
}

Set-Location $Root
docker compose up -d postgres redis
Write-Step "Containers started"

Write-Host "  Waiting for postgres" -NoNewline
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    $r = docker exec dbcreator-postgres-1 pg_isready -U dbcreator 2>&1
    if ($r -match "accepting connections") { $ready = $true; break }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 1
}
Write-Host ""
if (-not $ready) { Write-Fatal "Postgres did not become ready. Check: docker logs dbcreator-postgres-1" }
Write-Step "Postgres ready"

# ── 4. Python virtualenv + deps ───────────────────────────────────────────────
Write-Sec "Python dependencies"

if (-not (Test-Path $Venv)) {
    Write-Warn "Creating virtual environment..."
    & $PyCmd -m venv $Venv
}

& $VenvPip install -r (Join-Path $Backend "requirements.txt") --quiet
Write-Step "Packages installed"

# ── 5. Database migrations ────────────────────────────────────────────────────
Write-Sec "Database migrations"
Set-Location $Backend
& $VenvAlem upgrade head
Write-Step "Migrations up to date"

# ── 6. Node dependencies ──────────────────────────────────────────────────────
Write-Sec "Node dependencies"
$nodeModules = Join-Path $Frontend "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Warn "Running npm install (first time)..."
    npm --prefix $Frontend install
} else {
    Write-Step "node_modules already present"
}

# ── 7. Start servers in new windows ──────────────────────────────────────────
Write-Sec "Starting servers"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

# Kill any existing processes on these ports
@(8000, 5173) | ForEach-Object {
    $port = $_
    $pids = (netstat -ano 2>$null | Select-String ":$port ") -replace '.*\s+(\d+)$','$1' | Select-Object -Unique
    $pids | ForEach-Object {
        try { Stop-Process -Id ([int]$_.Trim()) -Force -ErrorAction SilentlyContinue } catch {}
    }
}

# Backend — new visible window
$backendCmd = "Set-Location '$Backend'; Write-Host 'Backend starting...' -ForegroundColor Cyan; & '$VenvPy' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $backendCmd -WindowStyle Normal
Write-Step "Backend window opened (port 8000)"

Start-Sleep -Seconds 1

# Frontend — new visible window
$frontendCmd = "Set-Location '$Frontend'; Write-Host 'Frontend starting...' -ForegroundColor Cyan; npm run dev; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $frontendCmd -WindowStyle Normal
Write-Step "Frontend window opened (port 5173)"

# ── 8. Seed ───────────────────────────────────────────────────────────────────
Write-Sec "Seeding database"

$adminKey = (Get-Content $EnvFile | Select-String "^ADMIN_KEY=") -replace "^ADMIN_KEY=", ""

Write-Host "  Waiting for API" -NoNewline
$apiUp = $false
for ($i = 0; $i -lt 20; $i++) {
    try {
        $h = Invoke-WebRequest "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($h.StatusCode -eq 200) { $apiUp = $true; break }
    } catch {}
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
}
Write-Host ""

if ($apiUp) {
    try {
        $seedHeaders = @{ "X-Admin-Key" = $adminKey; "Content-Type" = "application/json" }
        Invoke-RestMethod "http://localhost:8000/api/v1/admin/seed" -Method POST -Headers $seedHeaders -ErrorAction Stop | Out-Null
        Write-Step "Database seeded"
    } catch {
        Write-Warn "Seed skipped (already done or API not ready)"
    }
} else {
    Write-Warn "API did not respond in time. Seed manually once the server is up."
}

# ── Done ──────────────────────────────────────────────────────────────────────
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
Write-Host "  Stop:   .\Installation\stop.ps1" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green

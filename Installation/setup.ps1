#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root            = Split-Path $PSScriptRoot -Parent
$BackendEnvFile  = Join-Path (Join-Path $Root "backend") ".env"
$FrontendEnvFile = Join-Path (Join-Path $Root "frontend") ".env"

function Write-Step  { param($msg) Write-Host "  " -NoNewline; Write-Host "OK " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Fatal { param($msg) Write-Host "`n  ERROR: $msg" -ForegroundColor Red; exit 1 }

function New-RandomHex { param([int]$Bytes = 32)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buf = New-Object byte[] $Bytes
    $rng.GetBytes($buf)
    ($buf | ForEach-Object { $_.ToString('x2') }) -join ''
}
function New-FernetKey {
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buf = New-Object byte[] 32
    $rng.GetBytes($buf)
    [System.Convert]::ToBase64String($buf).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}

Write-Host "================================================================="
Write-Host "             DB Creator -- Setup & Start"
Write-Host "================================================================="

# 1. backend/.env
if (-not (Test-Path $BackendEnvFile)) {
    $FernetKey = New-FernetKey
    $JwtSecret = New-RandomHex 32
    $AdminKey  = New-RandomHex 16
    $AdminPass = New-RandomHex 12
    @"
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=$FernetKey
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=$AdminKey
JWT_SECRET=$JwtSecret
DEFAULT_ADMIN_PASSWORD=$AdminPass
"@ | Set-Content $BackendEnvFile -Encoding utf8
    Write-Step "Created backend/.env with generated secrets"
    Write-Host ""
    Write-Host "  Admin credentials (save these):" -ForegroundColor Cyan
    Write-Host "    Username: admin"
    Write-Host "    Password: $AdminPass"
    Write-Host "    Admin key: $AdminKey"
    Write-Host ""
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

# 4. Detect compose command (v2 plugin preferred, v1 standalone fallback)
$null = docker compose version 2>$null
if ($LASTEXITCODE -eq 0) {
    function Invoke-Compose { docker compose @args }
    $DCCmd = "docker compose"
} elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    function Invoke-Compose { docker-compose @args }
    $DCCmd = "docker-compose"
} else {
    Write-Fatal "Neither 'docker compose' nor 'docker-compose' found. Install Docker Compose and re-run."
}
Write-Step "Compose: $DCCmd"

# 5. Start
Set-Location $Root
Write-Host ""
Write-Host "  Starting all services (first run builds images -- takes a few minutes)..." -ForegroundColor Cyan
Invoke-Compose up -d
if ($LASTEXITCODE -ne 0) { Write-Fatal "$DCCmd up failed. Check output above." }

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "  All systems go!" -ForegroundColor Green
Write-Host "-----------------------------------------------------------------" -ForegroundColor Green
Write-Host "  Frontend  ->  http://localhost:5173" -ForegroundColor Green
Write-Host "  Backend   ->  http://localhost:8000" -ForegroundColor Green
Write-Host "  API docs  ->  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "-----------------------------------------------------------------" -ForegroundColor Green
Write-Host "  Login:  admin / (see password printed above, or check backend/.env)" -ForegroundColor Green
Write-Host "-----------------------------------------------------------------" -ForegroundColor Green
Write-Host "  Logs:   $DCCmd logs -f" -ForegroundColor Green
Write-Host "  Stop:   .\Installation\stop.ps1" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
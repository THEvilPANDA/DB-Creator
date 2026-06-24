# Full Docker Compose Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docker compose up` start the entire DB Creator stack — Postgres, Redis, migrations, API, ARQ worker, Vite frontend, and a one-shot seeder — with hot-reload working for backend and frontend.

**Architecture:** Add `frontend/Dockerfile` and five new Compose services (`migrate`, `worker`, `seed`, `frontend`, plus healthcheck on `postgres`). Override `DATABASE_URL`/`REDIS_URL` at the service level so `.env` stays valid for local dev. Slim the `setup.*` and `stop.*` scripts down to env-file creation + `docker compose up/down`.

**Tech Stack:** Docker Compose v2, Python 3.12-slim (backend image), Node 20-alpine (frontend image), Vite 5, uvicorn `--reload`, arq

## Global Constraints

- Do NOT change any backend Python source files except what is explicitly listed.
- `backend/.env` and `frontend/.env` are gitignored — never commit them.
- Keep `--profile monitoring` opt-in for Prometheus/Grafana unchanged.
- Worker hot-reload is intentionally NOT implemented (ARQ has no `--reload`); `docker compose restart worker` is the documented workflow.
- The pre-existing `USAGE` privilege bug in seed templates is out of scope.

---

### Task 1: Frontend Dockerfile + configurable Vite proxy

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `frontend/vite.config.ts`

**Interfaces:**
- Produces: `frontend/Dockerfile` that builds a Vite dev image; `VITE_API_PROXY_TARGET` env var consumed by `vite.config.ts` to set the proxy target

- [ ] **Step 1: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
```

- [ ] **Step 2: Verify the image builds**

```bash
docker build -t db-creator-frontend-test ./frontend
```

Expected: Build completes with no errors, final line like `Successfully built <id>` or `writing image sha256:...`.

- [ ] **Step 3: Update `frontend/vite.config.ts` to read proxy target from env**

Replace the current file with:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    proxy: {
      '/api': API_TARGET,
      '/health': API_TARGET,
    },
  },
})
```

- [ ] **Step 4: Verify local dev still works with the default**

Start the backend locally (or skip if Docker is the only way to run it). The config change is backward-compatible: without `VITE_API_PROXY_TARGET` set, the proxy falls back to `http://localhost:8000`, same as before.

If you can't run locally, verify by inspecting: `VITE_API_PROXY_TARGET` unset → `API_TARGET` must equal `'http://localhost:8000'`. Check the fallback in the source.

- [ ] **Step 5: Clean up test image**

```bash
docker rmi db-creator-frontend-test
```

- [ ] **Step 6: Commit**

```bash
git add frontend/Dockerfile frontend/vite.config.ts
git commit -m "feat: add frontend Dockerfile and configurable Vite proxy target"
```

---

### Task 2: Full docker-compose.yml rewrite

**Files:**
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `frontend/Dockerfile` (Task 1)
- Produces: All seven services wired up; healthchecks on `postgres` and `api`; `DATABASE_URL`/`REDIS_URL` overridden to Docker-internal hostnames for `migrate`, `api`, `worker`, `seed`

- [ ] **Step 1: Replace `docker-compose.yml` with the full updated version**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dbcreator
      POSTGRES_PASSWORD: dbcreator
      POSTGRES_DB: dbcreator
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dbcreator"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  migrate:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://dbcreator:dbcreator@postgres:5432/dbcreator
    depends_on:
      postgres:
        condition: service_healthy
    command: alembic upgrade head
    restart: "no"

  api:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://dbcreator:dbcreator@postgres:5432/dbcreator
      REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_started
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    healthcheck:
      test:
        - CMD-SHELL
        - "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health/database', timeout=3)\""
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s

  worker:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://dbcreator:dbcreator@postgres:5432/dbcreator
      REDIS_URL: redis://redis:6379/0
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_started
    volumes:
      - ./backend:/app
    command: python -m arq app.workers.worker.WorkerSettings
    restart: unless-stopped

  seed:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://dbcreator:dbcreator@postgres:5432/dbcreator
    depends_on:
      api:
        condition: service_healthy
    command: >
      python -c "
      import httpx, os;
      r = httpx.post(
        'http://api:8000/api/v1/admin/seed',
        headers={'X-Admin-Key': os.environ.get('ADMIN_KEY', '')},
        timeout=30
      );
      print(r.text)
      "
    restart: "no"

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_PROXY_TARGET: http://api:8000
    depends_on:
      - api
    volumes:
      - ./frontend:/app
      - /app/node_modules

  # Monitoring stack — start with: docker compose --profile monitoring up
  prometheus:
    image: prom/prometheus:v2.54.0
    profiles: ["monitoring"]
    ports:
      - "9090:9090"
    volumes:
      - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=15d
    depends_on:
      - api

  grafana:
    image: grafana/grafana:11.2.0
    profiles: ["monitoring"]
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH: /var/lib/grafana/dashboards/dbcreator.json
    volumes:
      - grafana_data:/var/lib/grafana
      - ./docker/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./docker/grafana/dashboards:/var/lib/grafana/dashboards:ro
    depends_on:
      - prometheus

volumes:
  postgres_data:
  prometheus_data:
  grafana_data:
```

- [ ] **Step 2: Validate compose file syntax**

```bash
docker compose config
```

Expected: Prints the resolved YAML with no errors. Scroll through and confirm all seven main services (`postgres`, `redis`, `migrate`, `api`, `worker`, `seed`, `frontend`) appear with correct `depends_on` and `healthcheck` blocks.

- [ ] **Step 3: Ensure `backend/.env` exists (create if not)**

The compose file uses `env_file: ./backend/.env`. If it doesn't exist yet, create it:

```bash
# Only if the file does not exist:
cp backend/.env.example backend/.env   # if .env.example exists
# OR create manually with these values:
cat > backend/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=dev-admin-key
JWT_SECRET=dev-jwt-secret-change-in-production
DEFAULT_ADMIN_PASSWORD=admin123
EOF
```

Note: `DATABASE_URL` in `.env` still uses `localhost` — this is intentional for local dev. The compose file overrides it with `postgres` (Docker hostname) for containers.

- [ ] **Step 4: Also ensure `frontend/.env` exists**

```bash
echo "VITE_ADMIN_KEY=dev-admin-key" > frontend/.env
```

- [ ] **Step 5: Start the full stack**

```bash
docker compose up
```

Watch the log output. Expected sequence:
1. `postgres` becomes healthy (you'll see `pg_isready` passing)
2. `migrate` runs and exits: look for `INFO  [alembic.runtime.migration] Running upgrade ...`
3. `api` starts and passes its healthcheck: look for `Application startup complete`
4. `seed` fires: look for JSON output with `"templates_created"` and `"admin_created"`
5. `worker` starts: look for `Starting arq worker`
6. `frontend` starts: look for `VITE vX.X.X ready`

- [ ] **Step 6: Verify each service is healthy**

Open a second terminal:

```bash
docker compose ps
```

Expected: All services show `running` or `exited (0)` for one-shots (`migrate`, `seed`). No service should show `restarting` or `exited (1)`.

```bash
# API health
curl http://localhost:8000/health/database
# Expected: {"status":"ok"}

# Frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173
# Expected: 200

# Seed worked — admin user exists
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | grep access_token
# Expected: line containing "access_token"
```

- [ ] **Step 7: Verify hot-reload works**

Edit any Python file in `backend/app/` — add a harmless comment and save.  
Watch the `api` container logs: uvicorn should print `Reloading...` within 1-2 seconds.

Edit any file in `frontend/src/` — save it.  
The browser tab at `http://localhost:5173` should update without a full page refresh.

- [ ] **Step 8: Stop and commit**

```bash
docker compose down
git add docker-compose.yml
git commit -m "feat: full docker compose stack — migrate, worker, seed, frontend services"
```

---

### Task 3: Slim down setup scripts

**Files:**
- Modify: `Installation/setup.ps1`
- Modify: `Installation/setup.sh`

**Interfaces:**
- Produces: Scripts that create `.env` files if missing, check Docker is running, then delegate entirely to `docker compose up -d`

- [ ] **Step 1: Replace `Installation/setup.ps1`**

```powershell
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root            = Split-Path $PSScriptRoot -Parent
$BackendEnvFile  = Join-Path $Root "backend" ".env"
$FrontendEnvFile = Join-Path $Root "frontend" ".env"

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
Write-Host "  Starting all services (first run builds images — takes a few minutes)..." -ForegroundColor Cyan
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
```

- [ ] **Step 2: Replace `Installation/setup.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}OK${NC}  $1"; }
fatal(){ echo -e "\n  ${RED}ERROR:${NC} $1"; exit 1; }

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              DB Creator — Setup & Start                         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"

# 1. backend/.env
BACKEND_ENV="$ROOT/backend/.env"
if [ ! -f "$BACKEND_ENV" ]; then
  cat > "$BACKEND_ENV" <<'EOF'
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=dev-admin-key
JWT_SECRET=dev-jwt-secret-change-in-production
DEFAULT_ADMIN_PASSWORD=admin123
EOF
  ok "Created backend/.env"
else
  ok "backend/.env exists"
fi

# 2. frontend/.env
FRONTEND_ENV="$ROOT/frontend/.env"
if [ ! -f "$FRONTEND_ENV" ]; then
  echo "VITE_ADMIN_KEY=dev-admin-key" > "$FRONTEND_ENV"
  ok "Created frontend/.env"
else
  ok "frontend/.env exists"
fi

# 3. Docker check
command -v docker &>/dev/null || fatal "Docker not found. Install Docker Engine and re-run."
docker info &>/dev/null        || fatal "Docker is not running. Start it and re-run."
ok "Docker running"

# 4. Start
cd "$ROOT"
echo ""
echo -e "  ${CYAN}Starting all services (first run builds images — takes a few minutes)...${NC}"
docker compose up -d

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  All systems go!                                                 ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Frontend  →  http://localhost:5173                              ║"
echo "║  Backend   →  http://localhost:8000                              ║"
echo "║  API docs  →  http://localhost:8000/docs                         ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Login:  admin / admin123                                        ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Logs:   docker compose logs -f                                  ║"
echo "║  Stop:   bash Installation/stop.sh                               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
```

- [ ] **Step 3: Verify the scripts are executable (Linux/Mac)**

```bash
chmod +x Installation/setup.sh
```

- [ ] **Step 4: Smoke test**

Run the script. Since services are already running from Task 2, `docker compose up -d` should print `... is up-to-date` for each container and exit immediately.

**Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File .\Installation\setup.ps1
```

**Linux:**
```bash
bash Installation/setup.sh
```

Expected: `.env` files already exist → `OK  backend/.env exists` / `OK  frontend/.env exists`. Docker is running → `OK  Docker running`. `docker compose up -d` exits immediately. "All systems go!" banner prints.

- [ ] **Step 5: Commit**

```bash
git add Installation/setup.ps1 Installation/setup.sh
git commit -m "feat: slim setup scripts to docker compose up"
```

---

### Task 4: Simplify stop scripts

**Files:**
- Modify: `Installation/stop.ps1`
- Modify: `Installation/stop.sh`

**Interfaces:**
- Produces: Scripts that run `docker compose down` from the project root

- [ ] **Step 1: Replace `Installation/stop.ps1`**

```powershell
$Root = Split-Path $PSScriptRoot -Parent
Write-Host "Stopping DB Creator..."
Set-Location $Root
docker compose down
Write-Host "Done."
```

- [ ] **Step 2: Replace `Installation/stop.sh`**

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
echo "Stopping DB Creator..."
cd "$ROOT"
docker compose down
echo "Done."
```

- [ ] **Step 3: Verify stop works**

```bash
bash Installation/stop.sh   # or .\Installation\stop.ps1 on Windows
```

Expected:
```
Stopping DB Creator...
[+] Running 7/7
 ✔ Container ...frontend...  Removed
 ✔ Container ...seed...      Removed
 ✔ Container ...worker...    Removed
 ✔ Container ...api...       Removed
 ✔ Container ...migrate...   Removed
 ✔ Container ...redis...     Removed
 ✔ Container ...postgres...  Removed
Done.
```

Then confirm nothing is left:
```bash
docker compose ps
```
Expected: Empty table (no running containers).

- [ ] **Step 4: Start again to confirm round-trip**

```bash
bash Installation/setup.sh   # or setup.ps1
```

Expected: Services come back up, `docker compose ps` shows all running.

- [ ] **Step 5: Commit**

```bash
git add Installation/stop.ps1 Installation/stop.sh
git commit -m "feat: simplify stop scripts to docker compose down"
```

---

### Task 5: Update documentation

**Files:**
- Modify: `Installation/INSTALL.md`
- Modify: `README.md`

- [ ] **Step 1: Replace `Installation/INSTALL.md`**

```markdown
# DB Creator — Installation Guide

Enterprise PostgreSQL provisioning platform.

> **Git repository:** https://github.com/THEvilPANDA/DB-Creator

---

## Prerequisites

| Tool | Notes |
|------|-------|
| Git | Any version |
| Docker Desktop | Windows / Mac — get it from [docker.com](https://www.docker.com). Linux: `docker.io` + `docker-compose-plugin` via apt. |

That's it. Python and Node run inside Docker — you don't need them locally.

---

## Quick start (new machine)

### 1 — Clone

```bash
git clone https://github.com/THEvilPANDA/DB-Creator.git
cd DB-Creator
```

### 2 — Start Docker Desktop

Open Docker Desktop and wait for the whale icon to appear in your taskbar/system tray before continuing.

### 3 — Run the setup script

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\Installation\setup.ps1
```

**Linux / Mac:**
```bash
bash Installation/setup.sh
```

The script:
1. Creates `backend/.env` and `frontend/.env` with dev defaults (if missing)
2. Checks that Docker is running
3. Runs `docker compose up -d`

Docker pulls images and builds containers on the first run — this takes a few minutes. Subsequent starts are fast.

### 4 — Open the app

| | URL |
|-|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

**Default login:** `admin` / `admin123`

---

## Day-to-day use

### Start

```powershell
# Windows
.\Installation\setup.ps1

# Linux / Mac
bash Installation/setup.sh
```

Or directly:
```bash
docker compose up -d
```

### Stop

```powershell
# Windows
.\Installation\stop.ps1

# Linux / Mac
bash Installation/stop.sh
```

Or directly:
```bash
docker compose down
```

### Logs

```bash
docker compose logs -f           # all services
docker compose logs -f api       # backend only
docker compose logs -f frontend  # Vite only
docker compose logs -f worker    # ARQ worker only
```

---

## Hot-reload

| Service | Reloads on save? |
|---------|-----------------|
| Backend (`api`) | Yes — uvicorn `--reload` watches `backend/` |
| Frontend | Yes — Vite HMR |
| Worker | **No** — run `docker compose restart worker` after changing worker code |

---

## Monitoring (optional)

```bash
docker compose --profile monitoring up -d
```

| | URL |
|-|-----|
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (login: admin / admin) |

---

## Configuration

`backend/.env` and `frontend/.env` are created automatically on first run and are gitignored. Copy them manually when moving to a new machine.

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator` | Used for local dev only; Docker overrides this to `postgres:5432` internally |
| `REDIS_URL` | `redis://localhost:6379/0` | Same — Docker overrides to `redis:6379` |
| `FERNET_KEY` | *(static dev key)* | Keep stable — encrypts stored credentials |
| `ADMIN_KEY` | `dev-admin-key` | Required header for `/admin/*` endpoints |
| `JWT_SECRET` | `dev-jwt-secret-change-in-production` | **Change in production** |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | Used by the seed service to create the first admin user |
| `VITE_ADMIN_KEY` | `dev-admin-key` | Frontend header for admin-gated API calls |

---

## Transferring to another machine

```bash
# 1. Push your code
git push

# 2. On the new machine
git clone https://github.com/THEvilPANDA/DB-Creator.git
cd DB-Creator
# Copy backend/.env and frontend/.env from the old machine (or let setup recreate defaults)
powershell -ExecutionPolicy Bypass -File .\Installation\setup.ps1   # Windows
# bash Installation/setup.sh                                          # Linux
```

To carry existing database data:
```bash
# On OLD machine — export
docker exec db-creator-postgres-1 pg_dump -U dbcreator dbcreator > backup.sql

# On NEW machine — import (after docker compose up)
docker exec -i db-creator-postgres-1 psql -U dbcreator dbcreator < backup.sql
```

---

## Troubleshooting

**`docker compose up` fails on first run with a build error**  
Check your internet connection — Docker needs to pull base images. Re-run after connecting.

**Port already in use (5173 or 8000)**  
Stop whatever is using the port, then `docker compose down` and `docker compose up -d` again.

**Migrations fail**  
Check Postgres logs: `docker compose logs postgres`

**Seed didn't create the admin user**  
Re-run seed manually:
```bash
curl -X POST http://localhost:8000/api/v1/admin/seed \
  -H "X-Admin-Key: dev-admin-key" \
  -H "Content-Type: application/json"
```

**Backend changes aren't hot-reloading**  
Confirm the `api` container has the volume mount: `docker compose ps` → `api` should be running. If you edited files outside `backend/`, those changes aren't mounted.

**Worker not picking up jobs**  
Check worker logs: `docker compose logs -f worker`. If you changed worker code, run `docker compose restart worker`.
```

- [ ] **Step 2: Update the Quick Start section in `README.md`**

Replace the existing Quick Start section (everything from `## Quick Start` through the end of step 4 / Frontend block) with:

```markdown
## Quick Start

**Prerequisite:** [Docker Desktop](https://www.docker.com) (includes Docker Compose). Python and Node are not required locally — they run inside containers.

### 1. Clone

```bash
git clone https://github.com/THEvilPANDA/DB-Creator.git
cd DB-Creator
```

### 2. Start

**Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File .\Installation\setup.ps1
```

**Linux / Mac:**
```bash
bash Installation/setup.sh
```

Or, if `.env` files already exist:
```bash
docker compose up -d
```

First run builds Docker images — takes a few minutes. Subsequent starts are instant.

### 3. Open

| | URL |
|-|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |

**Login:** `admin` / `admin123`

### Stop

```bash
docker compose down
```
```

- [ ] **Step 3: Review both docs**

Read through `INSTALL.md` and `README.md` and confirm:
- No mention of manual pip install, virtualenv, or npm install steps
- No mention of opening separate terminal windows
- Hot-reload caveats are present (worker requires restart)
- Transfer instructions reference `db-creator-postgres-1` container name (correct, matching compose project name `db-creator`)

- [ ] **Step 4: Commit**

```bash
git add Installation/INSTALL.md README.md
git commit -m "docs: rewrite install guide and readme for docker compose workflow"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `postgres` healthcheck → Task 2
- ✅ `migrate` one-shot service → Task 2
- ✅ `api` healthcheck using `/health/database` → Task 2
- ✅ `worker` service → Task 2
- ✅ `seed` one-shot → Task 2
- ✅ `frontend` service with `VITE_API_PROXY_TARGET` → Tasks 1 and 2
- ✅ `DATABASE_URL`/`REDIS_URL` Docker-internal overrides → Task 2
- ✅ Hot-reload via volume mounts → Task 2 (volumes in api and frontend services)
- ✅ `node_modules` anonymous volume → Task 2 (`/app/node_modules`)
- ✅ `--host` flag for Vite → Task 1 (`CMD ["npm", "run", "dev", "--", "--host"]`)
- ✅ Slim setup scripts → Task 3
- ✅ Slim stop scripts → Task 4
- ✅ Docs update → Task 5
- ✅ Worker hot-reload caveat documented → Task 5

**No placeholders found.**

**Type/name consistency:** `VITE_API_PROXY_TARGET` defined in Task 1 (vite.config.ts), set in Task 2 (compose environment). `db-creator-postgres-1` used consistently (compose project name is `db-creator` from directory name `DB-Creator` lowercased). All service names referenced in `depends_on` match service keys.

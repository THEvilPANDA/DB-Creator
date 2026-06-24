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

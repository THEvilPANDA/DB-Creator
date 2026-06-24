# DB Creator — Installation Guide

Enterprise PostgreSQL provisioning platform.

> **Git repository:** https://github.com/THEvilPANDA/DB-Creator

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Git | any | |
| Docker Desktop | 4.x | Windows / Mac — Linux uses `docker.io` |
| Python | 3.11+ | |
| Node.js | 18+ | |

The setup script installs missing tools automatically (Windows via `winget`, Ubuntu via `apt`).

---

## Quick start (new machine)

### 1 — Clone the repo

```bash
git clone https://github.com/THEvilPANDA/DB-Creator.git
cd db-creator
```

### 2 — Run the setup script

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\Installation\setup.ps1
```

**Ubuntu / Linux:**
```bash
bash Installation/setup.sh
```

That's it. The script handles everything:
- installs missing prerequisites
- creates `backend/.env` with safe dev defaults
- pulls and starts the Postgres + Redis Docker containers
- creates a Python virtualenv and installs dependencies
- runs all database migrations (`alembic upgrade head`)
- installs Node dependencies (`npm install`)
- starts the backend (port **8000**) and frontend (port **5173**) in separate terminal windows
- seeds the database with default templates and an `admin` user

### 3 — Open the app

| | URL |
|-|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

**Default login:** `admin` / `admin123`  
Change the password after first login.

---

## Day-to-day use

Re-run the same script any time to start the app. It skips steps that are already done (migrations, npm install, venv creation).

**Windows:**
```powershell
.\Installation\setup.ps1
```

**Ubuntu:**
```bash
bash Installation/setup.sh
```

---

## Stopping the app

**Windows:**
```powershell
.\Installation\stop.ps1
```

**Ubuntu:**
```bash
bash Installation/stop.sh
```

---

## Configuration

`backend/.env` is created automatically on first run but **is not committed to git** (it contains secrets).  
Copy it to new machines manually, or recreate it from the table below.

| Variable | Default (dev) | Notes |
|----------|--------------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator` | |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `FERNET_KEY` | *(generated)* | Keep this value stable — it encrypts stored credentials |
| `ADMIN_KEY` | `dev-admin-key` | Header secret for `/admin/*` endpoints |
| `JWT_SECRET` | `dev-jwt-secret-change-in-production` | **Change in production** |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | Used by `/admin/seed` to create the first admin user |

---

## Transferring to another PC

1. **Push your code** (if you haven't already):
   ```bash
   git remote add origin https://github.com/THEvilPANDA/DB-Creator.git
   git push -u origin master
   ```

2. **On the new machine** — clone and run:
   ```bash
   git clone https://github.com/THEvilPANDA/DB-Creator.git
   cd db-creator
   # Copy backend/.env from the old machine (or recreate it)
   powershell -ExecutionPolicy Bypass -File .\Installation\setup.ps1   # Windows
   # bash Installation/setup.sh                                          # Ubuntu
   ```

3. **Bring existing data** (optional):
   ```bash
   # On OLD machine — export:
   docker exec dbcreator-postgres-1 pg_dump -U dbcreator dbcreator > backup.sql

   # On NEW machine — import (after containers are running):
   docker exec -i dbcreator-postgres-1 psql -U dbcreator dbcreator < backup.sql
   ```

---

## Logs

When started via the setup script, server logs are written to:

```
logs/backend.log
logs/frontend.log
```

Tail them live:
```bash
tail -f logs/backend.log
tail -f logs/frontend.log
```

---

## Troubleshooting

**Docker not starting on Windows**  
Open Docker Desktop from the Start menu and wait for the whale icon in the system tray before re-running the script.

**Port already in use**  
Run `stop.ps1` / `stop.sh` first, then re-run setup.

**Migrations fail**  
Ensure Postgres is healthy: `docker logs dbcreator-postgres-1`

**`python3` resolves to the Microsoft Store stub**  
Install Python from [python.org](https://python.org) or run:
```powershell
winget install Python.Python.3.11
```
Then open a fresh terminal before re-running setup.

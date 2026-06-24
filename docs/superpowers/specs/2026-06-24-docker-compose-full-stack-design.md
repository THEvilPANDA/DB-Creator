# Design: Full Docker Compose Stack

**Date:** 2026-06-24  
**Status:** Approved

## Goal

Replace the current "open 3 PowerShell windows" setup with a single `docker compose up` that starts everything — Postgres, Redis, API, ARQ worker, and the Vite frontend — with hot-reload working for both backend and frontend.

## Non-goals

- Production hardening (this is a dev-mode compose)
- Fixing the pre-existing `USAGE` privilege bug in seed templates (separate issue)

---

## Service Graph

```
postgres  (healthcheck: pg_isready -U dbcreator)
    └──► migrate   one-shot: alembic upgrade head
              ├──► api      healthcheck: GET /health/database
              │       └──► seed   one-shot: POST /admin/seed
              └──► worker   python -m arq ...; no auto-reload

redis ─────────► api, worker  (env override in compose)

frontend  depends_on: api started (not healthy — Vite starts independently)
          Vite dev server bound to 0.0.0.0 via --host flag
          anonymous volume shadows node_modules to avoid host/container mismatch
```

**Startup order enforced by Docker Compose:**
1. `postgres` passes healthcheck (`pg_isready`)
2. `migrate` runs `alembic upgrade head`, exits 0
3. `api` and `worker` start (both blocked on `migrate: service_completed_successfully`)
4. `api` passes its healthcheck (`GET /health/database` returns `{"status":"ok"}`)
5. `seed` fires once (`POST /admin/seed`), exits — idempotent, safe to re-run
6. `frontend` starts (only requires `api` to be started, not healthy)

Monitoring stack (`prometheus`, `grafana`) keeps existing `--profile monitoring` opt-in. No changes.

---

## Files Changed

### `docker-compose.yml`

Add to existing file:

- **`postgres`**: add `healthcheck` (`pg_isready -U dbcreator`, interval 5s, retries 10)
- **`migrate`**: new one-shot service; image from `./backend`; `restart: "no"`; `depends_on: postgres: condition: service_healthy`; overrides DATABASE_URL to `postgresql+asyncpg://dbcreator:dbcreator@postgres:5432/dbcreator`; `command: alembic upgrade head`
- **`api`**: update `depends_on` to include `migrate: service_completed_successfully`; add `healthcheck` (`GET /health/database`, interval 10s, retries 10, start_period 10s); add environment override for DATABASE_URL and REDIS_URL (Docker-internal hostnames)
- **`worker`**: new service; `build: ./backend`; `env_file: ./backend/.env`; environment overrides for DATABASE_URL and REDIS_URL; volume mount `./backend:/app`; `command: python -m arq app.workers.worker.WorkerSettings`; `depends_on: migrate: service_completed_successfully, redis: service_started`; `restart: unless-stopped`
- **`seed`**: new one-shot service; `build: ./backend`; `env_file: ./backend/.env`; environment override for DATABASE_URL; `depends_on: api: condition: service_healthy`; `restart: "no"`; `command: python -c "import httpx, os; r = httpx.post('http://api:8000/api/v1/admin/seed', headers={'X-Admin-Key': os.environ.get('ADMIN_KEY','')}, timeout=30); print(r.text)"`
- **`frontend`**: new service; `build: ./frontend`; `ports: 5173:5173`; `volumes: [./frontend:/app, /app/node_modules]`; `environment: VITE_API_PROXY_TARGET=http://api:8000`; `command: npm run dev -- --host`; `depends_on: [api]`

### `frontend/Dockerfile`

New file. Uses `node:20-alpine`. Installs dependencies at build time so the anonymous volume trick works:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev", "--", "--host"]
```

The source volume mount (`./frontend:/app`) overrides the image's files at runtime, giving hot-reload. The anonymous volume at `/app/node_modules` preserves the container's node_modules so Windows host binaries don't leak in.

### `frontend/vite.config.ts`

Make proxy target configurable so it hits `api:8000` inside Docker and `localhost:8000` outside:

```typescript
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000';
// proxy: { '/api': API_TARGET, '/health': API_TARGET }
```

### `Installation/setup.ps1` and `Installation/setup.sh`

Shrink both to ~30 lines. Logic:

1. Create `backend/.env` from defaults if missing (same values as before)
2. Create `frontend/.env` with `VITE_ADMIN_KEY=dev-admin-key` if missing
3. Detect Docker running; fail clearly if not
4. Run `docker compose up -d`
5. Print URLs + login

### `Installation/stop.ps1` and `Installation/stop.sh`

Replace port-killing logic with `docker compose down`.

### `Installation/INSTALL.md` and `README.md`

Rewrite Quick Start to:
1. Clone
2. Run setup script (or manually create `.env` files)
3. `docker compose up` or `docker compose up -d`
4. Open http://localhost:5173

Document:
- Hot-reload: backend (uvicorn `--reload`) and frontend (Vite HMR) auto-reload on file save
- Worker: does NOT auto-reload; run `docker compose restart worker` after worker code changes
- Monitoring: `docker compose --profile monitoring up`
- Logs: `docker compose logs -f` or per-service `docker compose logs -f api`

---

## Caveats

- **Worker hot-reload**: ARQ has no `--reload` equivalent. Worker changes require `docker compose restart worker`.
- **First cold start**: Docker pulls/builds images on first run. Subsequent starts are fast.
- **Python 3.12 in Docker**: The backend Dockerfile uses `python:3.12-slim`. This is intentional — 3.12 is stable and avoids the PEP 749 issues that required unpinning packages for local Python 3.14 use. Both work with the current `>=` version constraints.
- **`.env` files**: `backend/.env` and `frontend/.env` are gitignored. The setup script creates them on first run. Copy them manually when moving to a new machine.

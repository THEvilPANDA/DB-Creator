# DB Creator

Enterprise API-first PostgreSQL provisioning platform.

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

---

## Development

### Run tests

```bash
cd backend

# Unit tests (no infrastructure needed)
python -m pytest tests/test_models.py tests/test_services.py tests/test_provisioner.py -v

# Integration tests (requires running Postgres)
docker compose up -d postgres
alembic upgrade head
python -m pytest tests/api/ -v
```

### Register a server with live capacity

When registering a server, provide `admin_dsn` to enable live capacity checks:

```bash
curl -X POST http://localhost:8000/api/v1/servers \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "local-pg",
    "host": "localhost",
    "port": 5432,
    "environment": "development",
    "admin_dsn": "postgresql://dbcreator:dbcreator@localhost:5432/dbcreator"
  }'
```

Without `admin_dsn`, capacity endpoints return `health: "unknown"` — jobs still submit normally.

### Submit a provisioning job

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"environment": "development", "owner": "alice", "db_name": "myapp_db"}'
```

- `development` / `staging` → auto-approved, status becomes `queued`
- `production` → status stays `pending` until approved via `POST /api/v1/jobs/{id}/approve`

---

## Project Layout

```
backend/
  app/
    models/       SQLModel ORM tables (8 tables, soft-delete)
    schemas/      Pydantic v2 request/response shapes
    api/v1/       Thin FastAPI route handlers
    services/     Business logic (approval, naming, capacity, placement, events)
    services/provisioner/  DatabaseProvisioner ABC + PostgreSQLProvisioner
    workers/      Arq task functions
  migrations/     Alembic versions
  tests/          Unit + integration tests

frontend/         Vite + React + TypeScript UI
docker/           Postgres init SQL
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator` | Metadata DB |
| `REDIS_URL` | `redis://localhost:6379/0` | Arq job queue |
| `ENVIRONMENT` | `development` | Affects approval policy |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | Allowed frontend origins |
| `FERNET_KEY` | _(empty)_ | Encryption key for sensitive fields (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |

For the frontend: copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_URL` if your backend isn't on `localhost:8000`.

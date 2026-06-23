# DB Creator

Enterprise API-first PostgreSQL provisioning platform.

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 18+

### 1. Start infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL 16 (port 5432) and Redis 7 (port 6379).

### 2. Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Copy and configure env
cp .env.example .env

# Apply migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 3. Arq worker

```bash
cd backend
arq app.workers.worker.WorkerSettings
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

- UI: http://localhost:5173

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

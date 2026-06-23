# DB Creator — Architecture

## Overview

DB Creator is an **API-first internal platform** for provisioning and managing PostgreSQL databases across environments. The UI is a thin consumer of the REST API. All business logic — provisioning, naming, approval, capacity checking, placement — lives exclusively in the backend. Every UI action has a corresponding REST endpoint, enabling CLI, CI/CD, Slack bots, and ERP systems to integrate without a frontend.

## System Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Consumers: Web UI · CLI · Jenkins/GH Actions · Slack Bot   │
└───────────────────────┬─────────────────────────────────────┘
                        │  REST  /api/v1/
┌───────────────────────▼─────────────────────────────────────┐
│  FastAPI  (app/main.py + app/api/v1/)                       │
│  Thin route handlers — validate, call service, return       │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│  Service Layer  (app/services/)                             │
│  ApprovalService · NamingService · CapacityService          │
│  PlacementService · EventPublisher                          │
└──────────┬─────────────────────────┬───────────────────────┘
           │                         │
┌──────────▼──────────┐   ┌──────────▼──────────────────────┐
│  Arq Workers        │   │  Provisioner Layer               │
│  (Redis queue)      │   │  DatabaseProvisioner ABC         │
│  provision_database │   │  PostgreSQLProvisioner (asyncpg) │
└──────────┬──────────┘   └──────────┬───────────────────────┘
           │                         │
┌──────────▼─────────────────────────▼───────────────────────┐
│  PostgreSQL Metadata Database                               │
│  servers · jobs · approval_requests · naming_profiles       │
│  database_templates · request_templates                     │
│  creation_logs · audit_logs                                 │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. API-First
Every UI action has a corresponding REST endpoint. The React frontend has zero business logic — it only calls APIs and renders responses. This enables immediate CLI, Jenkins, GitHub Actions, and ERP integration.

### 2. Abstract Provisioner
`DatabaseProvisioner` (ABC in `app/services/provisioner/base.py`) defines the engine contract. `PostgreSQLProvisioner` implements it with `asyncpg`. Adding MySQL or MongoDB means writing a new concrete class — no API, UI, or service layer changes needed.

### 3. Soft Delete
All major entities (`Server`, `Job`, `NamingProfile`, `DatabaseTemplate`, `RequestTemplate`, `CreationLog`) are never hard-deleted. They carry `is_deleted`, `deleted_at`, `deleted_by`. List endpoints exclude soft-deleted records by default. `AuditLog` is immutable — append-only, never deleted.

### 4. Approval Policy
Stored in config (Phase 0). `development` and `staging` auto-approve; `production` requires manual approval. An `ApprovalRequest` record is always created regardless of policy — auto-approved ones get `status=approved`, `approver=system`.

### 5. Async Job Execution
Job provisioning is async. The submit endpoint creates a `Job` record (queued or pending based on approval). An Arq task `provision_database(ctx, job_id)` runs the provisioner, emits domain events, and writes a `CreationLog`. Redis is the broker.

### 6. Domain Events
In-process `EventPublisher` emits `DomainEvent` dataclasses after state transitions. Subscribers register handlers at startup. Ready to swap for Redis Streams or RabbitMQ without changing emitter code.

## Directory Structure

```
backend/
├── app/
│   ├── main.py              FastAPI app, lifespan, CORS
│   ├── config.py            pydantic-settings Settings
│   ├── database.py          async engine + get_session dependency
│   ├── models/              SQLModel table classes (8 tables)
│   ├── schemas/             Pydantic v2 request/response shapes
│   ├── api/v1/              Thin route handlers
│   ├── services/
│   │   ├── provisioner/     DatabaseProvisioner ABC + PostgreSQLProvisioner
│   │   ├── approval.py      Approval policy evaluation
│   │   ├── naming.py        Pattern resolver + name validation
│   │   ├── capacity.py      Capacity gate logic
│   │   ├── placement.py     Server selection strategies
│   │   └── events.py        In-process domain event publisher
│   └── workers/             Arq task functions + WorkerSettings
└── migrations/              Alembic versions
```

## Running Locally

```bash
# Start infrastructure
docker compose up -d postgres redis

# Install dependencies
cd backend && pip install -r requirements.txt

# Apply migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload
```

- OpenAPI docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Start Arq worker: `arq app.workers.worker.WorkerSettings`

## Running Tests

```bash
cd backend
python -m pytest -v
```

Unit tests (models, services, provisioner) run without any infrastructure.
API integration tests require the test database (`dbcreator_test` on localhost:5432).

# DB Creator — Phase 0 Design Spec

**Date:** 2026-06-24  
**Scope:** Phase 0 — Project skeleton, PostgreSQL metadata DB, abstract provisioner, core models, FastAPI structure, kanban.md  
**Author:** Claude (from user spec `DB_Creator_Claude_Prompt.md`)

---

## Overview

DB Creator is an API-first internal platform for provisioning and managing PostgreSQL databases across environments. Every capability is exposed via REST. All provisioning, naming, approval, and placement logic lives exclusively in the backend. The UI is a thin consumer.

Phase 0 delivers the foundation: project scaffold, metadata database schema, abstract provisioner interface, and all core models.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Runtime | Python 3.12 | LTS, best async support |
| Framework | FastAPI | async-native, OpenAPI auto-docs |
| ORM | SQLModel + SQLAlchemy 2.0 | unified model+schema, async sessions |
| API schemas | Pydantic v2 (separate from ORM) | clean I/O shape control |
| Metadata DB | PostgreSQL 16 | concurrent jobs, locking, audit |
| Task queue | Arq + Redis | async-native, lightweight, persistent |
| Migrations | Alembic | full migration control, no auto-create |
| Config | pydantic-settings + .env | type-safe config, 12-factor |
| Frontend | Vite + React + TypeScript (stub) | Phase 0 scaffold only |
| Local infra | Docker Compose | Postgres + Redis + API |

---

## Project Layout

```
G:\AI\DBCreator\
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan hooks, middleware
│   │   ├── config.py            # pydantic-settings Settings class
│   │   ├── database.py          # async engine, session factory, get_session dep
│   │   ├── models/
│   │   │   ├── base.py          # TimestampMixin, SoftDeleteMixin
│   │   │   ├── server.py
│   │   │   ├── job.py
│   │   │   ├── approval.py
│   │   │   ├── naming_profile.py
│   │   │   ├── database_template.py
│   │   │   ├── request_template.py
│   │   │   ├── creation_log.py
│   │   │   └── audit_log.py
│   │   ├── schemas/             # Pydantic v2 request/response models (per domain)
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py    # Aggregates all sub-routers
│   │   │       ├── jobs.py
│   │   │       ├── servers.py
│   │   │       ├── history.py
│   │   │       ├── naming_profiles.py
│   │   │       ├── database_templates.py
│   │   │       ├── request_templates.py
│   │   │       └── health.py
│   │   ├── services/
│   │   │   ├── provisioner/
│   │   │   │   ├── base.py      # Abstract DatabaseProvisioner ABC
│   │   │   │   └── postgresql.py # PostgreSQLProvisioner (asyncpg)
│   │   │   ├── naming.py        # Naming engine + collision detection
│   │   │   ├── approval.py      # Approval policy evaluation
│   │   │   ├── capacity.py      # Server capacity metrics
│   │   │   ├── placement.py     # Placement strategies
│   │   │   └── events.py        # Domain event publisher (in-process)
│   │   └── workers/
│   │       └── tasks.py         # Arq job functions
│   ├── migrations/              # Alembic migration versions
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
├── frontend/                    # Vite+React+TS scaffold (Phase 0: stub only)
├── docs/
│   ├── architecture.md
│   └── superpowers/specs/
├── kanban.md
├── docker-compose.yml
└── CLAUDE.md
```

---

## Data Model

### Mixins (base.py)

**TimestampMixin** — `created_at`, `updated_at` (auto-managed)  
**SoftDeleteMixin** — `is_deleted: bool = False`, `deleted_at: datetime | None`, `deleted_by: str | None`

All major entities inherit both mixins. `AuditLog` inherits only `TimestampMixin` (never deleted).

### Core Models

**Server**
- `id`, `name`, `host`, `port`, `engine` (default: `postgresql`), `environment` (dev/staging/prod/client), `region`, `is_active`
- Capacity thresholds: `max_connections`, `max_storage_gb`, `warning_threshold_pct`, `critical_threshold_pct`
- Soft-delete: yes

**Job**
- `id`, `db_name` (final resolved name), `environment`, `status` (Pending/Queued/Running/Succeeded/Failed/Cancelled)
- FKs: `server_id`, `naming_profile_id`, `db_template_id`, `request_template_id`
- Ownership: `owner`, `team`, `cost_center`
- Timing: `expires_at`, `started_at`, `completed_at`
- Output: `error_message`
- Soft-delete: yes

**ApprovalRequest**
- `id`, `job_id` (FK), `approver`, `status` (Pending/Approved/Rejected), `comments`, `decided_at`
- No soft-delete (immutable audit record)

**NamingProfile**
- `id`, `name`, `pattern` (template string e.g. `{env}_{team}_{purpose}`), `prefix`, `suffix`, `separator`, `reserved_names` (JSON array), `allow_collision: bool`
- Soft-delete: yes

**DatabaseTemplate**
- `id`, `name`, `description`, `extensions` (JSON list), `permissions` (JSON object)
- Soft-delete: yes

**RequestTemplate**
- `id`, `name`, `environment`, `db_template_id` (FK, nullable), `naming_profile_id` (FK, nullable), `expiration_days`, `cost_center`, `team`, `description`
- Soft-delete: yes

**CreationLog**
- `id`, `job_id` (FK), `server_id` (FK), `db_name`, `db_user`, `connection_uri` (encrypted at rest), `iac_yaml`, `iac_terraform`, `provisioned_at`
- Soft-delete: yes

**AuditLog**
- `id`, `actor`, `action`, `entity_type`, `entity_id`, `payload` (JSON), `ip_address`, `created_at`
- Never deleted, no soft-delete mixin

---

## API Endpoints (Phase 0)

All under `/api/v1/`. Handlers are thin — they validate input, call a service, return a response.

```
# Jobs
POST   /api/v1/jobs                          Submit provisioning job
GET    /api/v1/jobs/{id}                     Job detail + status
GET    /api/v1/jobs/{id}/events              SSE stream (real-time status)
DELETE /api/v1/jobs/{id}                     Cancel job (soft)

# Servers
POST   /api/v1/servers                       Register server
GET    /api/v1/servers                       List (excludes soft-deleted by default)
GET    /api/v1/servers/{id}
PUT    /api/v1/servers/{id}
DELETE /api/v1/servers/{id}                  Soft delete
GET    /api/v1/servers/{id}/capacity         Live capacity metrics

# History
GET    /api/v1/history                       Paginated creation log

# Naming Profiles
POST/GET     /api/v1/naming-profiles
GET/PUT/DELETE /api/v1/naming-profiles/{id}

# Database Templates
POST/GET     /api/v1/database-templates
GET/PUT/DELETE /api/v1/database-templates/{id}

# Request Templates
POST/GET     /api/v1/request-templates
GET/PUT/DELETE /api/v1/request-templates/{id}

# Approvals
POST   /api/v1/approvals/{job_id}/decide    Approve or reject

# Health + Observability
GET    /health
GET    /health/database
GET    /health/queue
GET    /metrics                              Prometheus
```

---

## Provisioner Abstraction

```python
# services/provisioner/base.py
class DatabaseProvisioner(ABC):
    @abstractmethod
    async def create_database(self, spec: DatabaseSpec) -> DatabaseResult: ...
    @abstractmethod
    async def create_user(self, spec: UserSpec) -> UserResult: ...
    @abstractmethod
    async def grant_permissions(self, spec: PermissionSpec) -> None: ...
    @abstractmethod
    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None: ...
    @abstractmethod
    async def get_capacity(self) -> CapacityMetrics: ...
    @abstractmethod
    async def database_exists(self, db_name: str) -> bool: ...
```

`PostgreSQLProvisioner` implements all methods using `asyncpg`. Future engines (MySQL, MongoDB) implement the same interface with zero API or UI changes.

`DatabaseSpec`, `UserSpec`, `PermissionSpec`, `CapacityMetrics`, `DatabaseResult`, `UserResult` are Pydantic dataclasses defined in `services/provisioner/base.py` alongside the ABC — they are the contract between callers and provisioner implementations.

---

## Approval Policy

Stored in config (Phase 0), not DB:

| Environment | Policy |
|---|---|
| `development` | Auto-approved — job goes directly to Queued |
| `staging` | Auto-approved by default, configurable |
| `production` | Mandatory — job stays Pending until approved |

`ApprovalRequest` record is created for all jobs regardless of policy. For auto-approved jobs, it is created with `status=Approved` and `approver="system"`.

---

## Domain Events (Phase 0 skeleton)

In-process publisher. Events are dataclasses emitted synchronously after state changes. Consumers subscribe via simple in-process registry. Ready to swap for Redis Streams / RabbitMQ later.

Events defined in Phase 0:
- `DatabaseRequested`
- `DatabaseProvisioningStarted`
- `DatabaseProvisioningCompleted`
- `DatabaseProvisioningFailed`

---

## Key Constraints

- No hard deletes on any major entity.
- No provisioning logic in frontend — ever.
- No `SQLModel.metadata.create_all()` — Alembic only.
- All sensitive values (DB URIs, passwords) encrypted at rest via `cryptography.fernet`.
- Phase 0 does not implement JWT auth — endpoints are open. Auth is Phase 7.
- Frontend is scaffolded but empty. All Phase 0 deliverables are backend.

---

## Assumptions

1. Python 3.12 available or installed via Docker.
2. Docker Desktop available for local Postgres + Redis.
3. Arq chosen for task queue (user confirmed).
4. `asyncpg` for PostgreSQL driver (async-native).
5. `alembic` with async support (`asyncpg` dialect).
6. Frontend scaffold via `npm create vite` — no components written in Phase 0.

# Multi-Engine Database Provisioner Design

**Date:** 2026-06-25  
**Status:** Approved  
**Scope:** Add MySQL, MongoDB, pgvector, and Qdrant provisioning support alongside existing PostgreSQL

---

## Goal

Extend DB Creator to provision databases on five engine types: PostgreSQL (existing), pgvector, MySQL, MongoDB, and Qdrant — using a single unified provisioner interface and factory dispatch.

---

## Section 1: Core Architecture

**Keep the existing `DatabaseProvisioner` ABC unchanged.**

Add `options: dict = {}` to `DatabaseSpec` as a catch-all for engine-specific parameters (e.g., vector dimensions for pgvector, shard count for Qdrant). This avoids introducing engine-specific dataclasses while keeping the interface stable.

Add a `factory.py` module:

```python
# backend/app/services/provisioner/factory.py
from app.models.server import Server
from app.services.provisioner.base import DatabaseProvisioner

def get_provisioner(server: Server) -> DatabaseProvisioner:
    match server.engine:
        case "postgresql":  return PostgreSQLProvisioner(...)
        case "pgvector":    return PgvectorProvisioner(...)
        case "mysql":       return MySQLProvisioner(...)
        case "mongodb":     return MongoDBProvisioner(...)
        case "qdrant":      return QdrantProvisioner(...)
        case _:             raise ValueError(f"Unknown engine: {server.engine!r}")
```

All call sites (`tasks.py`, `servers.py`) use `get_provisioner(server)` instead of instantiating `PostgreSQLProvisioner` directly.

---

## Section 2: Provisioners

### pgvector (`pgvector.py`)

**IS-A PostgreSQLProvisioner** — subclass, not a peer. Overrides `enable_extensions` to prepend `"vector"` before the caller's list. Everything else inherits unchanged.

```python
class PgvectorProvisioner(PostgreSQLProvisioner):
    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        exts = ["vector"] + [e for e in extensions if e != "vector"]
        await super().enable_extensions(db_name, exts)
```

### MySQL (`mysql.py`)

Uses `aiomysql`. Implements all six abstract methods:
- `database_exists` → `SHOW DATABASES LIKE %s`
- `create_database` → `CREATE DATABASE IF NOT EXISTS`
- `create_user` → `CREATE USER IF NOT EXISTS … IDENTIFIED BY`
- `grant_permissions` → `GRANT … ON db.* TO user@'%'`
- `enable_extensions` → no-op (MySQL has no server-side extensions like PostgreSQL)
- `get_capacity` → `information_schema` size query + `SHOW STATUS LIKE 'Threads_connected'`

Admin DSN format: `mysql://user:pass@host:3306/`

### MongoDB (`mongodb.py`)

Uses `motor` (async MongoDB driver). MongoDB has no concept of "user per database" in OSS community edition, but the provisioner creates the database by inserting a sentinel document into a `_meta` collection (then removing it), which triggers DB creation in MongoDB's lazy model.

- `database_exists` → `list_database_names()`
- `create_database` → insert+delete sentinel doc to force creation
- `create_user` → `command("createUser", …)` in the target DB
- `grant_permissions` → no-op (roles handled at create_user step)
- `enable_extensions` → no-op
- `get_capacity` → `command("dbStats")` for db_count; `serverStatus` for connections

Admin DSN format: `mongodb://admin:pass@host:27017/`

### Qdrant (`qdrant.py`)

Uses `httpx` (already a dependency). Qdrant has no per-user auth in OSS — the API key is a single global token stored in `server.api_key`.

- `database_exists` → `GET /collections/{name}` → 200 = exists
- `create_database` → `PUT /collections/{name}` with `vectors` config from `spec.options`
- `create_user` → no-op
- `grant_permissions` → no-op
- `enable_extensions` → no-op
- `get_capacity` → `GET /collections` for db_count; disk from telemetry endpoint

Admin DSN format: `http://host:6333` (no credentials in DSN; API key stored separately in `server.api_key`)

---

## Section 3: Engine-Aware DB Console

### Backend (`databases.py`)

The existing `/databases/{log_id}/query` endpoint accepts a `sql: str` payload. This field is repurposed per engine:

| Engine | `sql` field content | Execution |
|---|---|---|
| postgresql / pgvector | SQL string | asyncpg (current) |
| mysql | SQL string | aiomysql |
| mongodb | JSON string `{"op":"find","coll":"name","filter":{}}` | motor |
| qdrant | JSON string `{"op":"search","coll":"name","limit":10}` | httpx |

The endpoint reads `server.engine` and dispatches accordingly. MongoDB and Qdrant results are normalised into the same `QueryResponse(columns, rows, row_count)` shape so the frontend table renders unchanged.

### Frontend (`Jobs.tsx`)

`DbConsole` receives the server (via `servers` prop, looked up by `log.server_id`). INSPECT and TEMPLATES arrays are selected by engine:

**PostgreSQL / pgvector:** current SQL arrays (unchanged). pgvector adds extra templates for `CREATE TABLE … (embedding vector(1536))` and `SELECT … ORDER BY embedding <-> '[…]'`.

**MySQL:** `SHOW TABLES`, `SHOW COLUMNS FROM …`, `SHOW CREATE TABLE …`, plus standard DML templates.

**MongoDB:** JSON templates using the `{"op":"find","coll":"…","filter":{},"limit":100}` protocol. Inspect shortcuts: list collections, collection stats, count documents.

**Qdrant:** JSON templates using `{"op":"search","coll":"…","limit":10}`. Inspect shortcuts: list collections, collection info, scroll points.

The console textarea placeholder changes by engine to give the user the right hint.

---

## Section 4: Server Model + UI

### Backend model changes

Add `api_key: Optional[str]` to the `Server` model (stored as `Text`, nullable). Used by the Qdrant provisioner. Never returned in `ServerRead` — exposed only as `has_api_key: bool` flag (same pattern as `admin_dsn`).

Add to `ServerCreate` and `ServerUpdate`. Create Alembic migration.

### Frontend `Servers.tsx`

**Engine dropdown** (new field in form, above Port):
```
postgresql | pgvector | mysql | mongodb | qdrant
```

**Dynamic defaults on engine change:**
- Port: pg/pgvector → 5432, mysql → 3306, mongodb → 27017, qdrant → 6333
- Admin DSN placeholder:
  - postgresql/pgvector: `postgresql://postgres:pass@host:5432/postgres`
  - mysql: `mysql://user:pass@host:3306/`
  - mongodb: `mongodb://admin:pass@host:27017/`
  - qdrant: `http://host:6333`
- Admin DSN label: rename to "Connection URL" for qdrant (no credentials in DSN)

**Qdrant-only field:** `api_key` password input, visible only when `engine === 'qdrant'`.

---

## Constraints

- Python ≥ 3.11, FastAPI ≥ 0.115, SQLModel ≥ 0.0.21
- New deps: `aiomysql>=2.0.1`, `motor>=3.3.0` (httpx already present)
- No breaking changes to existing PostgreSQL provisioning path
- `get_provisioner` is the single call-site change; existing provisioner ABC is unchanged except `DatabaseSpec.options`
- Qdrant OSS has no per-user auth — `create_user` and `grant_permissions` are no-ops that return success
- MongoDB `grant_permissions` is a no-op (roles assigned at create_user time)
- All engines normalise query results to `QueryResponse(columns, rows, row_count)` for uniform frontend rendering

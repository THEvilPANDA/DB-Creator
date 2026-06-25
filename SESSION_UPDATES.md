# Session Updates — 2026-06-24

All fixes applied to get the DB Creator app fully running on Windows with Python 3.14, Docker Desktop, and ngrok.

---

## Files Changed

### `Installation/setup.ps1`

1. **PATH refresh on startup** — added before all prerequisite checks so tools installed in a previous terminal session are found without opening a new window.

2. **Docker detection fix** — replaced `docker info 2>&1 | Out-Null; $dockerRunning = $?` with `$null = docker info 2>$null; $dockerRunning = ($LASTEXITCODE -eq 0)`. In PowerShell 5.1, `2>&1` on native commands wraps stderr in ErrorRecord objects and forces `$?` to `$false` even when the command succeeds.

3. **Container name fix** — `dbcreator-postgres-1` → `db-creator-postgres-1` (compose project name `db-creator` uses hyphens).

4. **Silent failure fix** — added `if ($LASTEXITCODE -ne 0) { Write-Fatal ... }` after pip install, alembic upgrade, and npm install. `$ErrorActionPreference = "Stop"` does not catch failures in native commands.

5. **ARQ worker added to startup** — setup now opens a third PowerShell window running `python -m arq app.workers.worker.WorkerSettings` alongside the backend and frontend.

---

### `backend/requirements.txt`

All core framework packages unpinned from exact versions (`==`) to minimum versions (`>=`) to allow pip to resolve Python 3.14-compatible releases:

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.6
sqlmodel>=0.0.21
sqlalchemy[asyncio]>=2.0.35
asyncpg>=0.29.0
alembic>=1.13.3
pydantic-settings>=2.5.2
arq>=0.26.1
```

**Why:** Python 3.14 introduced PEP 749 (deferred annotation evaluation) which broke older pinned versions of sqlmodel/pydantic. asyncpg 0.29.0 also had no pre-built wheel for 3.14 and required MSVC build tools.

---

### `backend/app/api/v1/jobs.py`

`datetime.now(timezone.utc)` → `datetime.now(timezone.utc).replace(tzinfo=None)` in two places where `decided_at` is set on `ApprovalRequest`.

**Why:** The `approval_requests` table column is `TIMESTAMP WITHOUT TIME ZONE`. asyncpg rejects inserting a timezone-aware datetime into a timezone-naive column.

---

### `backend/app/workers/tasks.py`

Same datetime fix applied to all `datetime.now(timezone.utc)` calls:
- `job.started_at`
- `log.provisioned_at`
- `job.completed_at` (in both success and `_fail` paths)

Also: removed `"USAGE"` from the default privileges list:
```python
# Before
privileges: list[str] = ["CONNECT", "USAGE", "CREATE"]
# After
privileges: list[str] = ["CONNECT", "CREATE"]
```
`USAGE` is a schema-level privilege, not valid for `GRANT ... ON DATABASE`.

---

### `backend/app/main.py`

Added logging to the ARQ pool startup so failures are visible instead of silently swallowed:

```python
# Before
except Exception:
    app.state.arq = None

# After
except Exception as e:
    print(f"[ARQ] Failed to connect to Redis, job enqueueing disabled: {e}")
    app.state.arq = None
```

---

### `backend/app/services/provisioner/base.py`

Fixed health status always returning `"critical"`:

```python
# Added at top of health property
if self.disk_free_gb == 0:
    return "healthy"
```

**Why:** `postgresql.py` hardcodes `disk_free_gb=0.0` (PostgreSQL has no OS-level free-disk query). The old formula computed `used / (used + 0) = 100%` → always critical, blocking all job submissions.

---

### `backend/app/services/provisioner/postgresql.py`

1. **CREATE USER password fix** — `ALTER USER ... PASSWORD $1` is not valid DDL syntax. Replaced with:
   ```python
   escaped_password = spec.password.replace("'", "''")
   await conn.execute(f"CREATE USER {user} WITH PASSWORD '{escaped_password}'")
   ```

2. **Idempotent user creation** — added a role-exists check so re-running a previously failed job doesn't error on "role already exists":
   ```python
   role_exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", spec.username)
   if role_exists:
       await conn.execute(f"ALTER USER {user} WITH PASSWORD '{escaped_password}'")
   else:
       await conn.execute(f"CREATE USER {user} WITH PASSWORD '{escaped_password}'")
   ```

3. **Removed USAGE from allowed privileges** — `USAGE` is not valid at the database level.

---

### `frontend/vite.config.ts`

Added `allowedHosts: true` to allow ngrok (and any other tunnel) to forward requests without Vite rejecting the Host header:

```typescript
server: {
  allowedHosts: true,
  proxy: { ... }
}
```

---

### `frontend/.env` *(new file — not in git)*

Created manually — not committed since it may contain secrets:

```
VITE_ADMIN_KEY=dev-admin-key
```

**Why:** The Settings page calls `/api/v1/admin/approval-policy` which requires the `X-Admin-Key` header. Without this file, `VITE_ADMIN_KEY` defaults to `""` and the request returns 403.

> **Do not set `VITE_API_URL` in this file.** Leaving it unset makes the frontend use relative paths (`/api/v1`) which are proxied by Vite to the local backend. Setting it to `http://localhost:8000/api/v1` breaks external access via ngrok because the browser tries to reach `localhost` on the visitor's machine.

---

## Manual One-Time Setup (do on new machine)

### 1. Set server `admin_dsn` after first run

The UI has no field for `admin_dsn` (it's intentionally hidden). After adding a server, set it via the API:

```powershell
$token = (Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body '{"username":"admin","password":"admin123"}').access_token

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/servers/1" -Method Put -ContentType 'application/json' `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{"name":"Localhost","host":"localhost","port":5432,"engine":"postgresql","environment":"development","admin_dsn":"postgresql://dbcreator:dbcreator@localhost:5432/postgres","max_connections":100,"max_storage_gb":100,"warning_threshold_pct":75,"critical_threshold_pct":90}'
```

> Use `postgres` as the target database in the DSN (not `dbcreator`). `CREATE DATABASE` must run outside any specific database connection.

### 2. Start the ARQ worker manually (if setup.ps1 window was closed)

```powershell
cd C:\DevOps\DB-Creator\backend
.\..\\.venv\Scripts\python.exe -m arq app.workers.worker.WorkerSettings
```

The worker must be running for job provisioning to happen. Jobs sit in `queued` status indefinitely without it.

### 3. ngrok (optional, for remote testing)

```powershell
ngrok http 5173
```

Only port 5173 (frontend) needs to be exposed. Vite proxies all `/api` calls to the local backend transparently. Requires ngrok authtoken on first use (`ngrok config add-authtoken <token>`).

---

## Known Remaining Issues

- **`app.state.arq` is None on API startup** — the backend's ARQ pool sometimes fails to initialise (exact cause not yet confirmed). Workaround: jobs submitted via the UI are saved as `queued` in the DB but not enqueued in Redis. Re-enqueue manually with:
  ```powershell
  cd C:\DevOps\DB-Creator\backend
  .\..\\.venv\Scripts\python.exe -c "
  import asyncio
  from arq import create_pool
  from arq.connections import RedisSettings
  from app.config import settings

  async def main():
      pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
      await pool.enqueue_job('provision_database', job_id=<JOB_ID>)
      await pool.aclose()

  asyncio.run(main())
  "
  ```
  Replace `<JOB_ID>` with the ID shown in the Jobs page.

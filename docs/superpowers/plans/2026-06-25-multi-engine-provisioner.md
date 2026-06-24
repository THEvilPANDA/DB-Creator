# Multi-Engine Database Provisioner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MySQL, MongoDB, pgvector, and Qdrant provisioning support alongside PostgreSQL, with an engine-aware DB console in both backend and frontend.

**Architecture:** Single `DatabaseProvisioner` ABC (unchanged) with four new concrete implementations; a `factory.py` factory dispatches by `server.engine`. The DB console backend routes queries by engine; the frontend selects templates by engine.

**Tech Stack:** Python/FastAPI backend (asyncpg, aiomysql, motor, httpx); React/TypeScript frontend; SQLModel/Alembic for DB schema; ARQ worker for async provisioning.

## Global Constraints

- Python ≥ 3.11; no walrus operators in tests; use `match` for engine dispatch in factory
- New deps: `aiomysql>=2.0.1`, `motor>=3.3.0` (httpx 0.27.2 already present — do not change its pin)
- `DatabaseProvisioner` ABC is **not** modified (no new abstract methods)
- Only add `options: dict = field(default_factory=dict)` to `DatabaseSpec` — no other changes to base dataclasses
- `get_provisioner(server)` is the single factory function; all provisioner instantiation goes through it
- No breaking changes to the existing PostgreSQL provisioning path
- Qdrant `create_user` and `grant_permissions` return `UserResult(success=True)` / `None` (no-op)
- MongoDB `grant_permissions` is a no-op
- All engines return `QueryResponse(columns, rows, row_count, error, status)` from the console endpoint
- Run tests with: `cd backend && python -m pytest tests/ -v`
- Alembic migrations run with: `cd backend && alembic upgrade head`

---

### Task 1: Add `options` to `DatabaseSpec` and factory module

**Files:**
- Modify: `backend/app/services/provisioner/base.py`
- Create: `backend/app/services/provisioner/factory.py`
- Modify: `backend/tests/test_provisioner.py`
- Create: `backend/tests/test_factory.py`

**Interfaces:**
- Produces: `DatabaseSpec.options: dict` (default `{}`)
- Produces: `get_provisioner(server: Server) -> DatabaseProvisioner` in `factory.py`
- Consumes: `Server.engine: str`, `Server.admin_dsn: str`, `Server.api_key: str | None` (api_key added in Task 7 — factory stubs it as `None` for now via `getattr`)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_factory.py
import pytest
from unittest.mock import MagicMock

def _server(engine, admin_dsn="postgresql://u:p@h/db", api_key=None):
    s = MagicMock()
    s.engine = engine
    s.admin_dsn = admin_dsn
    s.api_key = api_key
    s.id = 1
    s.warning_threshold_pct = 75.0
    s.critical_threshold_pct = 90.0
    s.host = "localhost"
    s.port = 5432
    return s

def test_factory_postgresql():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.postgresql import PostgreSQLProvisioner
    p = get_provisioner(_server("postgresql"))
    assert isinstance(p, PostgreSQLProvisioner)

def test_factory_pgvector():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.pgvector import PgvectorProvisioner
    p = get_provisioner(_server("pgvector"))
    assert isinstance(p, PgvectorProvisioner)

def test_factory_mysql():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.mysql import MySQLProvisioner
    p = get_provisioner(_server("mysql", admin_dsn="mysql://u:p@h/"))
    assert isinstance(p, MySQLProvisioner)

def test_factory_mongodb():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.mongodb import MongoDBProvisioner
    p = get_provisioner(_server("mongodb", admin_dsn="mongodb://u:p@h/"))
    assert isinstance(p, MongoDBProvisioner)

def test_factory_qdrant():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.qdrant import QdrantProvisioner
    p = get_provisioner(_server("qdrant", admin_dsn="http://localhost:6333"))
    assert isinstance(p, QdrantProvisioner)

def test_factory_unknown_raises():
    from app.services.provisioner.factory import get_provisioner
    with pytest.raises(ValueError, match="Unknown engine"):
        get_provisioner(_server("oracle"))

def test_database_spec_options_default():
    from app.services.provisioner.base import DatabaseSpec
    spec = DatabaseSpec(name="mydb", owner="alice")
    assert spec.options == {}

def test_database_spec_options_custom():
    from app.services.provisioner.base import DatabaseSpec
    spec = DatabaseSpec(name="mydb", owner="alice", options={"dimensions": 1536})
    assert spec.options == {"dimensions": 1536}
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_factory.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.provisioner.factory'`

- [ ] **Step 3: Add `options` to `DatabaseSpec`**

In `backend/app/services/provisioner/base.py`, add `options` field after `template`:

```python
@dataclass
class DatabaseSpec:
    name: str
    owner: str
    extensions: list[str] = field(default_factory=list)
    template: Optional[str] = None
    options: dict = field(default_factory=dict)
```

- [ ] **Step 4: Create the factory module**

```python
# backend/app/services/provisioner/factory.py
from app.services.provisioner.base import DatabaseProvisioner


def get_provisioner(server) -> DatabaseProvisioner:
    engine = server.engine
    admin_dsn = server.admin_dsn or ""
    api_key = getattr(server, "api_key", None)
    sid = server.id
    warn = server.warning_threshold_pct
    crit = server.critical_threshold_pct

    match engine:
        case "postgresql":
            from app.services.provisioner.postgresql import PostgreSQLProvisioner
            return PostgreSQLProvisioner(dsn=admin_dsn, server_id=sid,
                                        warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "pgvector":
            from app.services.provisioner.pgvector import PgvectorProvisioner
            return PgvectorProvisioner(dsn=admin_dsn, server_id=sid,
                                       warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mysql":
            from app.services.provisioner.mysql import MySQLProvisioner
            return MySQLProvisioner(dsn=admin_dsn, server_id=sid,
                                    warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mongodb":
            from app.services.provisioner.mongodb import MongoDBProvisioner
            return MongoDBProvisioner(dsn=admin_dsn, server_id=sid,
                                      warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "qdrant":
            from app.services.provisioner.qdrant import QdrantProvisioner
            return QdrantProvisioner(base_url=admin_dsn, api_key=api_key, server_id=sid,
                                     warning_threshold_pct=warn, critical_threshold_pct=crit)
        case _:
            raise ValueError(f"Unknown engine: {engine!r}")
```

- [ ] **Step 5: Run tests (will still fail — stubs needed for imports)**

```
cd backend && python -m pytest tests/test_factory.py -v
```
Expected: FAIL with `ModuleNotFoundError` for `pgvector`, `mysql`, `mongodb`, `qdrant` — this is fine, subsequent tasks create these.

For now, create empty stub files so the factory import tests can at least resolve:

```python
# backend/app/services/provisioner/pgvector.py  (stub — real impl in Task 2)
from app.services.provisioner.postgresql import PostgreSQLProvisioner
class PgvectorProvisioner(PostgreSQLProvisioner):
    pass
```

```python
# backend/app/services/provisioner/mysql.py  (stub — real impl in Task 3)
from app.services.provisioner.base import DatabaseProvisioner, DatabaseResult, DatabaseSpec, UserResult, UserSpec, PermissionSpec, CapacityMetrics
class MySQLProvisioner(DatabaseProvisioner):
    def __init__(self, dsn, server_id, warning_threshold_pct=75.0, critical_threshold_pct=90.0):
        pass
    async def create_database(self, spec): ...
    async def create_user(self, spec): ...
    async def grant_permissions(self, spec): ...
    async def enable_extensions(self, db_name, extensions): ...
    async def get_capacity(self): ...
    async def database_exists(self, db_name): ...
```

```python
# backend/app/services/provisioner/mongodb.py  (stub — real impl in Task 4)
from app.services.provisioner.base import DatabaseProvisioner, DatabaseResult, DatabaseSpec, UserResult, UserSpec, PermissionSpec, CapacityMetrics
class MongoDBProvisioner(DatabaseProvisioner):
    def __init__(self, dsn, server_id, warning_threshold_pct=75.0, critical_threshold_pct=90.0):
        pass
    async def create_database(self, spec): ...
    async def create_user(self, spec): ...
    async def grant_permissions(self, spec): ...
    async def enable_extensions(self, db_name, extensions): ...
    async def get_capacity(self): ...
    async def database_exists(self, db_name): ...
```

```python
# backend/app/services/provisioner/qdrant.py  (stub — real impl in Task 5)
from app.services.provisioner.base import DatabaseProvisioner
class QdrantProvisioner(DatabaseProvisioner):
    def __init__(self, base_url, api_key, server_id, warning_threshold_pct=75.0, critical_threshold_pct=90.0):
        pass
    async def create_database(self, spec): ...
    async def create_user(self, spec): ...
    async def grant_permissions(self, spec): ...
    async def enable_extensions(self, db_name, extensions): ...
    async def get_capacity(self): ...
    async def database_exists(self, db_name): ...
```

- [ ] **Step 6: Run factory tests — should now pass**

```
cd backend && python -m pytest tests/test_factory.py -v
```
Expected: All 8 tests PASS

- [ ] **Step 7: Run full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: All existing tests still pass (no regressions)

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/provisioner/base.py \
        backend/app/services/provisioner/factory.py \
        backend/app/services/provisioner/pgvector.py \
        backend/app/services/provisioner/mysql.py \
        backend/app/services/provisioner/mongodb.py \
        backend/app/services/provisioner/qdrant.py \
        backend/tests/test_factory.py
git commit -m "feat: add options to DatabaseSpec + engine factory + provisioner stubs"
```

---

### Task 2: pgvector provisioner (full implementation)

**Files:**
- Modify: `backend/app/services/provisioner/pgvector.py` (replace stub)
- Modify: `backend/tests/test_provisioner.py`

**Interfaces:**
- Consumes: `PostgreSQLProvisioner` (Task 1 complete)
- Produces: `PgvectorProvisioner` — identical API to PostgreSQLProvisioner but always enables `vector` extension first

- [ ] **Step 1: Add pgvector tests**

Append to `backend/tests/test_provisioner.py`:

```python
import inspect
from app.services.provisioner.pgvector import PgvectorProvisioner
from app.services.provisioner.postgresql import PostgreSQLProvisioner

def test_pgvector_is_subclass_of_postgresql():
    assert issubclass(PgvectorProvisioner, PostgreSQLProvisioner)

def test_pgvector_implements_all_abstract_methods():
    from app.services.provisioner.base import DatabaseProvisioner
    abstract_methods = {
        name for name, method in inspect.getmembers(DatabaseProvisioner)
        if getattr(method, "__isabstractmethod__", False)
    }
    assert abstract_methods.issubset(set(dir(PgvectorProvisioner)))

def test_pgvector_is_not_postgresql():
    p = PgvectorProvisioner(dsn="postgresql://u:p@h/db", server_id=1)
    assert type(p) is PgvectorProvisioner
```

- [ ] **Step 2: Run tests — the stub should already make subclass tests pass**

```
cd backend && python -m pytest tests/test_provisioner.py -v
```
Expected: PASS (stub is already a subclass)

- [ ] **Step 3: Implement full pgvector provisioner**

Replace `backend/app/services/provisioner/pgvector.py`:

```python
from app.services.provisioner.postgresql import PostgreSQLProvisioner


class PgvectorProvisioner(PostgreSQLProvisioner):
    """PostgreSQL provisioner that always enables the vector extension."""

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        # Prepend 'vector'; deduplicate while preserving remaining order
        exts = ["vector"] + [e for e in extensions if e != "vector"]
        await super().enable_extensions(db_name, exts)
```

- [ ] **Step 4: Run tests**

```
cd backend && python -m pytest tests/test_provisioner.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/provisioner/pgvector.py backend/tests/test_provisioner.py
git commit -m "feat: implement pgvector provisioner (PostgreSQL subclass + auto-enable vector)"
```

---

### Task 3: MySQL provisioner (aiomysql)

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/services/provisioner/mysql.py` (replace stub)
- Create: `backend/tests/test_mysql_provisioner.py`

**Interfaces:**
- Produces: `MySQLProvisioner(dsn, server_id, warning_threshold_pct, critical_threshold_pct)`
- DSN format: `mysql://user:pass@host:port/` (trailing slash, no DB name — root connection)

- [ ] **Step 1: Add aiomysql to requirements**

In `backend/requirements.txt`, add after `asyncpg` line:
```
aiomysql>=2.0.1
```

- [ ] **Step 2: Write failing MySQL provisioner tests**

```python
# backend/tests/test_mysql_provisioner.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.provisioner.mysql import MySQLProvisioner
from app.services.provisioner.base import DatabaseSpec, UserSpec, PermissionSpec


def _provisioner():
    return MySQLProvisioner(
        dsn="mysql://root:secret@localhost:3306/",
        server_id=1,
        warning_threshold_pct=75.0,
        critical_threshold_pct=90.0,
    )


@pytest.mark.asyncio
async def test_mysql_database_exists_true():
    p = _provisioner()
    mock_conn = AsyncMock()
    mock_conn.fetchone.return_value = ("mydb",)
    with patch.object(p, "_connect", return_value=mock_conn):
        result = await p.database_exists("mydb")
    assert result is True
    mock_conn.execute.assert_called_once_with("SHOW DATABASES LIKE %s", ("mydb",))
    mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_mysql_database_exists_false():
    p = _provisioner()
    mock_conn = AsyncMock()
    mock_conn.fetchone.return_value = None
    with patch.object(p, "_connect", return_value=mock_conn):
        result = await p.database_exists("notexist")
    assert result is False


@pytest.mark.asyncio
async def test_mysql_create_database_success():
    p = _provisioner()
    mock_conn = AsyncMock()
    with patch.object(p, "database_exists", return_value=False), \
         patch.object(p, "_connect", return_value=mock_conn):
        result = await p.create_database(DatabaseSpec(name="newdb", owner="alice"))
    assert result.success is True
    assert result.db_name == "newdb"


@pytest.mark.asyncio
async def test_mysql_create_database_already_exists():
    p = _provisioner()
    with patch.object(p, "database_exists", return_value=True):
        result = await p.create_database(DatabaseSpec(name="existing", owner="alice"))
    assert result.success is False
    assert "already exists" in result.message


@pytest.mark.asyncio
async def test_mysql_create_user_success():
    p = _provisioner()
    mock_conn = AsyncMock()
    mock_conn.fetchone.return_value = None  # user doesn't exist
    with patch.object(p, "_connect", return_value=mock_conn):
        result = await p.create_user(UserSpec(username="alice", password="pw", db_name="mydb"))
    assert result.success is True


@pytest.mark.asyncio
async def test_mysql_grant_permissions():
    p = _provisioner()
    mock_conn = AsyncMock()
    with patch.object(p, "_connect", return_value=mock_conn):
        await p.grant_permissions(PermissionSpec(db_name="mydb", username="alice", privileges=["SELECT", "INSERT"]))
    # Verify GRANT was called
    assert mock_conn.execute.called


@pytest.mark.asyncio
async def test_mysql_enable_extensions_noop():
    p = _provisioner()
    # Should complete without error — MySQL has no server extensions
    await p.enable_extensions("mydb", ["some_ext"])


@pytest.mark.asyncio
async def test_mysql_get_capacity():
    p = _provisioner()
    mock_conn = AsyncMock()
    # SHOW DATABASES
    mock_conn.fetchall.return_value = [("db1",), ("db2",)]
    # SHOW STATUS
    mock_conn.fetchone.return_value = ("Threads_connected", "5")
    with patch.object(p, "_connect", return_value=mock_conn):
        m = await p.get_capacity()
    assert m.server_id == 1
    assert isinstance(m.db_count, int)
```

- [ ] **Step 3: Run tests — expect FAIL (stub has no real implementation)**

```
cd backend && python -m pytest tests/test_mysql_provisioner.py -v
```
Expected: FAIL — stub methods return `None` / raise `NotImplementedError`

- [ ] **Step 4: Implement MySQL provisioner**

Replace `backend/app/services/provisioner/mysql.py`:

```python
import re
from urllib.parse import urlparse

import aiomysql

from app.services.provisioner.base import (
    CapacityMetrics,
    DatabaseProvisioner,
    DatabaseResult,
    DatabaseSpec,
    PermissionSpec,
    UserResult,
    UserSpec,
)

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")

_ALLOWED_PRIVILEGES = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALL PRIVILEGES"})


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return name


class MySQLProvisioner(DatabaseProvisioner):
    def __init__(
        self,
        dsn: str,
        server_id: int,
        warning_threshold_pct: float = 75.0,
        critical_threshold_pct: float = 90.0,
    ):
        parsed = urlparse(dsn)
        self._host = parsed.hostname or "localhost"
        self._port = parsed.port or 3306
        self._user = parsed.username or "root"
        self._password = parsed.password or ""
        self._server_id = server_id
        self._warning_threshold_pct = warning_threshold_pct
        self._critical_threshold_pct = critical_threshold_pct

    async def _connect(self) -> aiomysql.Connection:
        return await aiomysql.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            autocommit=True,
        )

    async def database_exists(self, db_name: str) -> bool:
        conn = await self._connect()
        try:
            await conn.execute("SHOW DATABASES LIKE %s", (db_name,))
            row = await conn.fetchone()
            return row is not None
        finally:
            conn.close()

    async def create_database(self, spec: DatabaseSpec) -> DatabaseResult:
        if await self.database_exists(spec.name):
            return DatabaseResult(db_name=spec.name, success=False,
                                  message=f"Database '{spec.name}' already exists")
        _validate_identifier(spec.name)
        conn = await self._connect()
        try:
            await conn.execute(f"CREATE DATABASE `{spec.name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            return DatabaseResult(db_name=spec.name, success=True)
        except Exception as exc:
            return DatabaseResult(db_name=spec.name, success=False, message=str(exc))
        finally:
            conn.close()

    async def create_user(self, spec: UserSpec) -> UserResult:
        _validate_identifier(spec.username)
        escaped_pw = spec.password.replace("'", "''")
        conn = await self._connect()
        try:
            await conn.execute("SELECT 1 FROM mysql.user WHERE user = %s AND host = '%%'", (spec.username,))
            exists = await conn.fetchone()
            if exists:
                await conn.execute(f"ALTER USER '{spec.username}'@'%%' IDENTIFIED BY '{escaped_pw}'")
            else:
                await conn.execute(f"CREATE USER '{spec.username}'@'%%' IDENTIFIED BY '{escaped_pw}'")
            return UserResult(username=spec.username, success=True)
        except Exception as exc:
            return UserResult(username=spec.username, success=False, message=str(exc))
        finally:
            conn.close()

    async def grant_permissions(self, spec: PermissionSpec) -> None:
        _validate_identifier(spec.db_name)
        _validate_identifier(spec.username)
        for priv in spec.privileges:
            if priv.upper() not in _ALLOWED_PRIVILEGES:
                raise ValueError(f"Privilege not allowed: {priv!r}")
        privs = ", ".join(p.upper() for p in spec.privileges)
        conn = await self._connect()
        try:
            await conn.execute(f"GRANT {privs} ON `{spec.db_name}`.* TO '{spec.username}'@'%%'")
            await conn.execute("FLUSH PRIVILEGES")
        finally:
            conn.close()

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        pass  # MySQL has no server-side extensions equivalent to PostgreSQL

    async def get_capacity(self) -> CapacityMetrics:
        conn = await self._connect()
        try:
            await conn.execute("SHOW DATABASES")
            rows = await conn.fetchall()
            db_count = len([r for r in rows if r[0] not in ("information_schema", "performance_schema", "mysql", "sys")])
            await conn.execute("SHOW STATUS LIKE 'Threads_connected'")
            status_row = await conn.fetchone()
            active_connections = int(status_row[1]) if status_row else 0
            return CapacityMetrics(
                server_id=self._server_id,
                db_count=db_count,
                active_connections=active_connections,
                disk_used_gb=0.0,
                disk_free_gb=0.0,
                warning_threshold_pct=self._warning_threshold_pct,
                critical_threshold_pct=self._critical_threshold_pct,
            )
        finally:
            conn.close()
```

- [ ] **Step 5: Run MySQL tests**

```
cd backend && python -m pytest tests/test_mysql_provisioner.py -v
```
Expected: All PASS

- [ ] **Step 6: Run full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: All PASS (including factory tests for MySQL)

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/services/provisioner/mysql.py backend/tests/test_mysql_provisioner.py
git commit -m "feat: implement MySQL provisioner (aiomysql)"
```

---

### Task 4: MongoDB provisioner (motor)

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/services/provisioner/mongodb.py` (replace stub)
- Create: `backend/tests/test_mongodb_provisioner.py`

**Interfaces:**
- Produces: `MongoDBProvisioner(dsn, server_id, warning_threshold_pct, critical_threshold_pct)`
- DSN format: `mongodb://admin:pass@host:27017/`

- [ ] **Step 1: Add motor to requirements**

In `backend/requirements.txt`, add:
```
motor>=3.3.0
```

- [ ] **Step 2: Write failing MongoDB provisioner tests**

```python
# backend/tests/test_mongodb_provisioner.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.services.provisioner.mongodb import MongoDBProvisioner
from app.services.provisioner.base import DatabaseSpec, UserSpec, PermissionSpec


def _provisioner():
    return MongoDBProvisioner(
        dsn="mongodb://admin:secret@localhost:27017/",
        server_id=2,
        warning_threshold_pct=75.0,
        critical_threshold_pct=90.0,
    )


@pytest.mark.asyncio
async def test_mongodb_database_exists_true():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=["mydb", "admin"])
    with patch.object(p, "_client", return_value=mock_client, new_callable=lambda: property):
        pass
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.database_exists("mydb")
    assert result is True


@pytest.mark.asyncio
async def test_mongodb_database_exists_false():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=["admin", "local"])
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.database_exists("notexist")
    assert result is False


@pytest.mark.asyncio
async def test_mongodb_create_database_success():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=[])
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
    mock_col.delete_many = AsyncMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.create_database(DatabaseSpec(name="newdb", owner="alice"))
    assert result.success is True


@pytest.mark.asyncio
async def test_mongodb_create_user_success():
    p = _provisioner()
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1.0})
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.create_user(UserSpec(username="alice", password="pw", db_name="mydb"))
    assert result.success is True


@pytest.mark.asyncio
async def test_mongodb_grant_permissions_noop():
    p = _provisioner()
    # grant_permissions is a no-op for MongoDB (roles assigned at create_user time)
    await p.grant_permissions(PermissionSpec(db_name="mydb", username="alice"))


@pytest.mark.asyncio
async def test_mongodb_enable_extensions_noop():
    p = _provisioner()
    await p.enable_extensions("mydb", ["ext"])


@pytest.mark.asyncio
async def test_mongodb_get_capacity():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=["mydb", "admin", "local"])
    mock_admin_db = MagicMock()
    mock_admin_db.command = AsyncMock(return_value={
        "connections": {"current": 3},
        "ok": 1.0,
    })
    mock_client.__getitem__ = MagicMock(return_value=mock_admin_db)
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        m = await p.get_capacity()
    assert m.server_id == 2
    assert isinstance(m.active_connections, int)
```

- [ ] **Step 3: Run tests — expect FAIL (stub)**

```
cd backend && python -m pytest tests/test_mongodb_provisioner.py -v
```
Expected: FAIL

- [ ] **Step 4: Implement MongoDB provisioner**

Replace `backend/app/services/provisioner/mongodb.py`:

```python
from motor.motor_asyncio import AsyncIOMotorClient

from app.services.provisioner.base import (
    CapacityMetrics,
    DatabaseProvisioner,
    DatabaseResult,
    DatabaseSpec,
    PermissionSpec,
    UserResult,
    UserSpec,
)

_SYSTEM_DBS = frozenset({"admin", "local", "config"})


class MongoDBProvisioner(DatabaseProvisioner):
    def __init__(
        self,
        dsn: str,
        server_id: int,
        warning_threshold_pct: float = 75.0,
        critical_threshold_pct: float = 90.0,
    ):
        self._dsn = dsn
        self._server_id = server_id
        self._warning_threshold_pct = warning_threshold_pct
        self._critical_threshold_pct = critical_threshold_pct

    def _client(self) -> AsyncIOMotorClient:
        return AsyncIOMotorClient(self._dsn, serverSelectionTimeoutMS=5000)

    async def database_exists(self, db_name: str) -> bool:
        client = self._client()
        try:
            names = await client.list_database_names()
            return db_name in names
        finally:
            client.close()

    async def create_database(self, spec: DatabaseSpec) -> DatabaseResult:
        if await self.database_exists(spec.name):
            return DatabaseResult(db_name=spec.name, success=False,
                                  message=f"Database '{spec.name}' already exists")
        client = self._client()
        try:
            # MongoDB creates DBs lazily; insert+delete a sentinel to force creation
            col = client[spec.name]["_meta"]
            result = await col.insert_one({"_init": True})
            await col.delete_many({"_id": result.inserted_id})
            return DatabaseResult(db_name=spec.name, success=True)
        except Exception as exc:
            return DatabaseResult(db_name=spec.name, success=False, message=str(exc))
        finally:
            client.close()

    async def create_user(self, spec: UserSpec) -> UserResult:
        client = self._client()
        try:
            db = client[spec.db_name]
            await db.command(
                "createUser",
                spec.username,
                pwd=spec.password,
                roles=[{"role": "readWrite", "db": spec.db_name}],
            )
            return UserResult(username=spec.username, success=True)
        except Exception as exc:
            msg = str(exc)
            # MongoDB raises if user exists — treat as idempotent success
            if "already exists" in msg.lower():
                return UserResult(username=spec.username, success=True)
            return UserResult(username=spec.username, success=False, message=msg)
        finally:
            client.close()

    async def grant_permissions(self, spec: PermissionSpec) -> None:
        pass  # Roles are assigned at create_user time in MongoDB

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        pass  # MongoDB has no server-side extensions

    async def get_capacity(self) -> CapacityMetrics:
        client = self._client()
        try:
            names = await client.list_database_names()
            db_count = len([n for n in names if n not in _SYSTEM_DBS])
            try:
                status = await client["admin"].command("serverStatus", repl=0, metrics=0, locks=0)
                active_connections = status.get("connections", {}).get("current", 0)
            except Exception:
                active_connections = 0
            return CapacityMetrics(
                server_id=self._server_id,
                db_count=db_count,
                active_connections=int(active_connections),
                disk_used_gb=0.0,
                disk_free_gb=0.0,
                warning_threshold_pct=self._warning_threshold_pct,
                critical_threshold_pct=self._critical_threshold_pct,
            )
        finally:
            client.close()
```

- [ ] **Step 5: Run MongoDB tests**

```
cd backend && python -m pytest tests/test_mongodb_provisioner.py -v
```
Expected: All PASS

- [ ] **Step 6: Run full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/services/provisioner/mongodb.py backend/tests/test_mongodb_provisioner.py
git commit -m "feat: implement MongoDB provisioner (motor)"
```

---

### Task 5: Qdrant provisioner (httpx)

**Files:**
- Modify: `backend/app/services/provisioner/qdrant.py` (replace stub)
- Create: `backend/tests/test_qdrant_provisioner.py`

**Interfaces:**
- Produces: `QdrantProvisioner(base_url, api_key, server_id, warning_threshold_pct, critical_threshold_pct)`
- `base_url` format: `http://host:6333`
- `api_key` is optional (OSS Qdrant accepts `None`)

- [ ] **Step 1: Write failing Qdrant provisioner tests**

```python
# backend/tests/test_qdrant_provisioner.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.provisioner.qdrant import QdrantProvisioner
from app.services.provisioner.base import DatabaseSpec, UserSpec, PermissionSpec


def _provisioner(api_key=None):
    return QdrantProvisioner(
        base_url="http://localhost:6333",
        api_key=api_key,
        server_id=3,
        warning_threshold_pct=75.0,
        critical_threshold_pct=90.0,
    )


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status_code
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.asyncio
async def test_qdrant_database_exists_true():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = _mock_response(200, {"result": {"name": "mycol"}})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        result = await p.database_exists("mycol")
    assert result is True


@pytest.mark.asyncio
async def test_qdrant_database_exists_false():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = _mock_response(404, {"status": {"error": "Not found"}})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        result = await p.database_exists("notexist")
    assert result is False


@pytest.mark.asyncio
async def test_qdrant_create_database_success():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    # database_exists returns False → proceed with PUT
    mock_client.get.return_value = _mock_response(404, {})
    mock_client.put.return_value = _mock_response(200, {"result": True})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        spec = DatabaseSpec(name="mycol", owner="alice", options={"size": 1536, "distance": "Cosine"})
        result = await p.create_database(spec)
    assert result.success is True


@pytest.mark.asyncio
async def test_qdrant_create_user_noop():
    p = _provisioner()
    result = await p.create_user(UserSpec(username="alice", password="pw", db_name="mycol"))
    assert result.success is True


@pytest.mark.asyncio
async def test_qdrant_grant_permissions_noop():
    p = _provisioner()
    await p.grant_permissions(PermissionSpec(db_name="mycol", username="alice"))


@pytest.mark.asyncio
async def test_qdrant_enable_extensions_noop():
    p = _provisioner()
    await p.enable_extensions("mycol", [])


@pytest.mark.asyncio
async def test_qdrant_get_capacity():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = _mock_response(200, {"result": {"collections": [{"name": "a"}, {"name": "b"}]}})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        m = await p.get_capacity()
    assert m.server_id == 3
    assert m.db_count == 2


@pytest.mark.asyncio
async def test_qdrant_api_key_included_in_headers():
    p = _provisioner(api_key="my-secret-key")
    headers = p._headers()
    assert headers.get("api-key") == "my-secret-key"


def test_qdrant_no_api_key_no_header():
    p = _provisioner(api_key=None)
    assert "api-key" not in p._headers()
```

- [ ] **Step 2: Run tests — expect FAIL**

```
cd backend && python -m pytest tests/test_qdrant_provisioner.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement Qdrant provisioner**

Replace `backend/app/services/provisioner/qdrant.py`:

```python
import httpx

from app.services.provisioner.base import (
    CapacityMetrics,
    DatabaseProvisioner,
    DatabaseResult,
    DatabaseSpec,
    PermissionSpec,
    UserResult,
    UserSpec,
)


class QdrantProvisioner(DatabaseProvisioner):
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        server_id: int,
        warning_threshold_pct: float = 75.0,
        critical_threshold_pct: float = 90.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._server_id = server_id
        self._warning_threshold_pct = warning_threshold_pct
        self._critical_threshold_pct = critical_threshold_pct

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            h["api-key"] = self._api_key
        return h

    async def database_exists(self, db_name: str) -> bool:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self._base_url}/collections/{db_name}",
                headers=self._headers(),
            )
            return r.status_code == 200

    async def create_database(self, spec: DatabaseSpec) -> DatabaseResult:
        if await self.database_exists(spec.name):
            return DatabaseResult(db_name=spec.name, success=False,
                                  message=f"Collection '{spec.name}' already exists")
        size = spec.options.get("size", 1536)
        distance = spec.options.get("distance", "Cosine")
        body = {"vectors": {"size": size, "distance": distance}}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.put(
                    f"{self._base_url}/collections/{spec.name}",
                    headers=self._headers(),
                    json=body,
                )
            if r.status_code in (200, 201):
                return DatabaseResult(db_name=spec.name, success=True)
            return DatabaseResult(db_name=spec.name, success=False, message=r.text)
        except Exception as exc:
            return DatabaseResult(db_name=spec.name, success=False, message=str(exc))

    async def create_user(self, spec: UserSpec) -> UserResult:
        return UserResult(username=spec.username, success=True)  # OSS Qdrant has no per-user auth

    async def grant_permissions(self, spec: PermissionSpec) -> None:
        pass  # No-op

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        pass  # No-op

    async def get_capacity(self) -> CapacityMetrics:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/collections", headers=self._headers())
            collections = r.json().get("result", {}).get("collections", []) if r.status_code == 200 else []
            db_count = len(collections)
        except Exception:
            db_count = 0
        return CapacityMetrics(
            server_id=self._server_id,
            db_count=db_count,
            active_connections=0,
            disk_used_gb=0.0,
            disk_free_gb=0.0,
            warning_threshold_pct=self._warning_threshold_pct,
            critical_threshold_pct=self._critical_threshold_pct,
        )
```

- [ ] **Step 4: Run Qdrant tests**

```
cd backend && python -m pytest tests/test_qdrant_provisioner.py -v
```
Expected: All PASS

- [ ] **Step 5: Run full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/provisioner/qdrant.py backend/tests/test_qdrant_provisioner.py
git commit -m "feat: implement Qdrant provisioner (httpx REST)"
```

---

### Task 6: Wire factory into tasks.py and servers.py

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/api/v1/servers.py`
- Modify: `backend/tests/test_services.py` (or create `backend/tests/test_tasks_factory.py`)

**Interfaces:**
- Consumes: `get_provisioner(server)` from `factory.py` (Task 1)
- Produces: `provision_database` dispatches to the correct provisioner by `server.engine`
- Produces: engine-aware `connection_uri` (postgresql://, mysql://, mongodb://, qdrant-specific)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_tasks_factory.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_server(engine="postgresql"):
    s = MagicMock()
    s.id = 1
    s.engine = engine
    s.admin_dsn = "postgresql://u:p@h/db"
    s.api_key = None
    s.host = "localhost"
    s.port = 5432
    s.warning_threshold_pct = 75.0
    s.critical_threshold_pct = 90.0
    return s


def _make_job(engine="postgresql"):
    j = MagicMock()
    j.id = 10
    j.status = "queued"
    j.server_id = 1
    j.db_name = "testdb"
    j.environment = "development"
    j.db_template_id = None
    j.owner = "alice"
    return j


@pytest.mark.asyncio
async def test_provision_uses_factory():
    """Verify provision_database calls get_provisioner, not PostgreSQLProvisioner directly."""
    from app.workers.tasks import provision_database

    mock_provisioner = AsyncMock()
    mock_provisioner.create_user.return_value = MagicMock(success=True)
    mock_provisioner.create_database.return_value = MagicMock(success=True, db_name="testdb")
    mock_provisioner.grant_permissions = AsyncMock()
    mock_provisioner.enable_extensions = AsyncMock()

    mock_session = AsyncMock()
    mock_session.get.side_effect = lambda model, pk: {
        (None, 10): _make_job(),
        (None, 1): _make_server(),
    }.get((model, pk), _make_job() if pk == 10 else _make_server())

    def _get_side_effect(model, pk):
        from app.models.job import Job
        from app.models.server import Server
        if model is Job:
            return _make_job()
        if model is Server:
            return _make_server()
        return None

    mock_session.get = AsyncMock(side_effect=_get_side_effect)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("app.workers.tasks.AsyncSessionLocal") as mock_session_factory, \
         patch("app.workers.tasks.get_provisioner", return_value=mock_provisioner) as mock_factory:
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await provision_database({}, job_id=10)

    mock_factory.assert_called_once()


@pytest.mark.asyncio
async def test_mysql_connection_uri_format():
    """Verify connection_uri uses correct scheme for MySQL."""
    from app.workers.tasks import _build_connection_uri
    uri = _build_connection_uri(
        engine="mysql", user="alice", password="pw", host="db", port=3306, db_name="mydb"
    )
    assert uri.startswith("mysql://")
    assert "mydb" in uri


@pytest.mark.asyncio
async def test_mongodb_connection_uri_format():
    from app.workers.tasks import _build_connection_uri
    uri = _build_connection_uri(
        engine="mongodb", user="alice", password="pw", host="db", port=27017, db_name="mydb"
    )
    assert uri.startswith("mongodb://")


@pytest.mark.asyncio
async def test_qdrant_connection_uri_format():
    from app.workers.tasks import _build_connection_uri
    uri = _build_connection_uri(
        engine="qdrant", user="", password="", host="db", port=6333, db_name="mycol"
    )
    assert "mycol" in uri
```

- [ ] **Step 2: Run tests — expect FAIL**

```
cd backend && python -m pytest tests/test_tasks_factory.py -v
```
Expected: FAIL — `get_provisioner` not imported in tasks.py, `_build_connection_uri` does not exist

- [ ] **Step 3: Update tasks.py**

Replace `backend/app/workers/tasks.py` with the following (full file):

```python
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.database import AsyncSessionLocal
from app.metrics import JOBS_COMPLETED, PROVISION_DURATION
from app.models.creation_log import CreationLog
from app.models.database_template import DatabaseTemplate
from app.models.job import Job
from app.models.server import Server
from app.services.audit import write_audit
from app.services.events import DomainEvent, publisher
from app.services.iac import generate_terraform, generate_yaml
from app.services.provisioner.base import DatabaseSpec, PermissionSpec, UserSpec
from app.services.provisioner.factory import get_provisioner


def _build_connection_uri(engine: str, user: str, password: str, host: str, port: int, db_name: str) -> str:
    if engine == "qdrant":
        return f"http://{host}:{port}/collections/{db_name}"
    scheme = {
        "postgresql": "postgresql",
        "pgvector": "postgresql",
        "mysql": "mysql",
        "mongodb": "mongodb",
    }.get(engine, "postgresql")
    return f"{scheme}://{user}:{password}@{host}:{port}/{db_name}"


async def provision_database(ctx: dict, job_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            return {"success": False, "error": "Job not found"}

        if not job.server_id:
            await _fail(session, job, "No server assigned to this job")
            return {"success": False, "error": "No server assigned"}

        server: Server | None = await session.get(Server, job.server_id)
        if not server or not server.admin_dsn:
            await _fail(session, job, "Server not found or has no admin_dsn — cannot provision")
            return {"success": False, "error": "Server missing credentials"}

        db_template: DatabaseTemplate | None = (
            await session.get(DatabaseTemplate, job.db_template_id) if job.db_template_id else None
        )

        _start = time.monotonic()
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(job)
        await write_audit(session, actor="worker", action="provision.start", entity_type="job",
                          entity_id=job_id, payload={"server_id": server.id})
        await session.commit()
        publisher.publish(DomainEvent("DatabaseProvisioningStarted", {"job_id": job_id}))

        try:
            provisioner = get_provisioner(server)

            extensions: list[str] = db_template.extensions if db_template else []
            privileges: list[str] = ["CONNECT", "CREATE"]
            if db_template and db_template.permissions:
                app_privs = db_template.permissions.get("app_user")
                if app_privs:
                    privileges = app_privs

            db_user = f"{job.db_name}_user"
            db_password = secrets.token_urlsafe(24)

            user_result = await provisioner.create_user(
                UserSpec(username=db_user, password=db_password, db_name=job.db_name)
            )
            if not user_result.success:
                raise RuntimeError(f"create_user failed: {user_result.message}")

            db_result = await provisioner.create_database(
                DatabaseSpec(name=job.db_name, owner=db_user, extensions=[])
            )
            if not db_result.success:
                raise RuntimeError(f"create_database failed: {db_result.message}")

            await provisioner.grant_permissions(
                PermissionSpec(db_name=job.db_name, username=db_user, privileges=privileges)
            )

            if extensions:
                await provisioner.enable_extensions(job.db_name, extensions)

            connection_uri = _build_connection_uri(
                engine=server.engine,
                user=db_user,
                password=db_password,
                host=server.host,
                port=server.port,
                db_name=job.db_name,
            )

            log = CreationLog(
                job_id=job.id,
                server_id=server.id,
                db_name=job.db_name,
                db_user=db_user,
                connection_uri=connection_uri,
                iac_yaml=generate_yaml(
                    db_name=job.db_name,
                    db_user=db_user,
                    host=server.host,
                    port=server.port,
                    environment=job.environment,
                    engine=server.engine,
                ),
                iac_terraform=generate_terraform(
                    db_name=job.db_name,
                    db_user=db_user,
                    host=server.host,
                    port=server.port,
                ),
                provisioned_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(log)

            elapsed = time.monotonic() - _start
            PROVISION_DURATION.labels(environment=job.environment).observe(elapsed)
            JOBS_COMPLETED.labels(status="succeeded", environment=job.environment).inc()

            job.status = "succeeded"
            job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(job)
            await write_audit(session, actor="worker", action="provision.complete", entity_type="job",
                              entity_id=job_id, payload={"db_name": job.db_name, "db_user": db_user,
                                                          "duration_s": round(elapsed, 2)})
            await session.commit()

            publisher.publish(DomainEvent(
                "DatabaseProvisioningCompleted",
                {"job_id": job_id, "db_name": job.db_name, "db_user": db_user},
            ))
            return {"success": True, "job_id": job_id, "db_name": job.db_name}

        except Exception as exc:
            JOBS_COMPLETED.labels(status="failed", environment=job.environment).inc()
            await _fail(session, job, str(exc)[:1000])
            publisher.publish(DomainEvent(
                "DatabaseProvisioningFailed", {"job_id": job_id, "error": str(exc)}
            ))
            return {"success": False, "error": str(exc)}


async def _fail(session, job: Job, message: str) -> None:
    job.status = "failed"
    job.error_message = message
    job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(job)
    await write_audit(session, actor="worker", action="provision.fail", entity_type="job",
                      entity_id=job.id, payload={"error": message[:500]})
    await session.commit()
```

- [ ] **Step 4: Update servers.py `_live_capacity` to use factory**

In `backend/app/api/v1/servers.py`, replace:

```python
from app.services.provisioner.postgresql import PostgreSQLProvisioner
```

with:

```python
from app.services.provisioner.factory import get_provisioner
```

And replace the `_live_capacity` function:

```python
async def _live_capacity(server: Server) -> CapacityMetrics:
    if not server.admin_dsn:
        return _UNKNOWN_CAPACITY(server.id)
    try:
        provisioner = get_provisioner(server)
        m = await asyncio.wait_for(provisioner.get_capacity(), timeout=5.0)
        return CapacityMetrics(
            server_id=m.server_id,
            db_count=m.db_count,
            active_connections=m.active_connections,
            disk_used_gb=m.disk_used_gb,
            disk_free_gb=m.disk_free_gb,
            health=m.health,
        )
    except Exception:
        return _UNKNOWN_CAPACITY(server.id)
```

- [ ] **Step 5: Run tests**

```
cd backend && python -m pytest tests/ -v
```
Expected: All PASS (including new `test_tasks_factory.py`)

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/api/v1/servers.py backend/tests/test_tasks_factory.py
git commit -m "feat: route provisioning through factory — all engines use get_provisioner()"
```

---

### Task 7: Add api_key to Server model and schemas

**Files:**
- Modify: `backend/app/models/server.py`
- Modify: `backend/app/schemas/server.py`
- Create: `backend/migrations/versions/d3e4f5a6b7c8_add_server_api_key.py`
- Modify: `backend/tests/api/test_servers.py`

**Interfaces:**
- Produces: `Server.api_key: Optional[str]`
- Produces: `ServerCreate.api_key: Optional[str]`, `ServerUpdate.api_key: Optional[str]`
- Produces: `ServerRead.has_api_key: bool` (same pattern as `has_admin_dsn`)

- [ ] **Step 1: Write failing test**

Add to `backend/tests/api/test_servers.py`:

```python
def test_server_read_exposes_has_api_key_not_api_key(client, auth_headers):
    """api_key must not appear in ServerRead; has_api_key bool must."""
    payload = {
        "name": "qdrant-test", "host": "localhost", "port": 6333, "engine": "qdrant",
        "environment": "development", "max_connections": 100, "max_storage_gb": 100.0,
        "warning_threshold_pct": 75.0, "critical_threshold_pct": 90.0,
        "api_key": "secret-key",
    }
    r = client.post("/api/v1/servers", json=payload, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert "api_key" not in body           # must not leak
    assert body["has_api_key"] is True     # flag must be present
```

- [ ] **Step 2: Run test — expect FAIL**

```
cd backend && python -m pytest tests/api/test_servers.py::test_server_read_exposes_has_api_key_not_api_key -v
```
Expected: FAIL — `api_key` field not accepted / `has_api_key` missing from response

- [ ] **Step 3: Add api_key to Server model**

In `backend/app/models/server.py`, after the `admin_dsn` line add:

```python
    api_key: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
```

- [ ] **Step 4: Update server schemas**

In `backend/app/schemas/server.py`:

Add `api_key: Optional[str] = None` to `ServerCreate` and `ServerUpdate`.

In `ServerRead`, add `has_api_key: bool = False` (it's already there for `has_admin_dsn`; add it next to it):

```python
    has_admin_dsn: bool = False
    has_api_key: bool = False
```

Update the `_populate_flags` validator to also populate `has_api_key`:

```python
    @model_validator(mode="before")
    @classmethod
    def _populate_flags(cls, v):
        if isinstance(v, dict):
            if "admin_dsn" in v:
                v.setdefault("has_admin_dsn", bool(v["admin_dsn"]))
            if "api_key" in v:
                v.setdefault("has_api_key", bool(v["api_key"]))
            return v
        d: dict = {}
        for fname in cls.model_fields:
            if fname == "has_admin_dsn":
                d["has_admin_dsn"] = bool(getattr(v, "admin_dsn", None))
            elif fname == "has_api_key":
                d["has_api_key"] = bool(getattr(v, "api_key", None))
            else:
                d[fname] = getattr(v, fname, None)
        return d
```

- [ ] **Step 5: Create Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "add_server_api_key"
```

Review the generated file in `backend/migrations/versions/` — it should contain:
```python
op.add_column('servers', sa.Column('api_key', sa.Text(), nullable=True))
```

If autogenerate missed it, write it manually:

```python
# backend/migrations/versions/<hash>_add_server_api_key.py
def upgrade() -> None:
    op.add_column('servers', sa.Column('api_key', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('servers', 'api_key')
```

Apply migration:
```bash
cd backend && alembic upgrade head
```

- [ ] **Step 6: Run tests**

```
cd backend && python -m pytest tests/api/test_servers.py -v
```
Expected: All PASS including the new `has_api_key` test

- [ ] **Step 7: Run full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/server.py backend/app/schemas/server.py \
        backend/migrations/versions/ backend/tests/api/test_servers.py
git commit -m "feat: add api_key to Server model (has_api_key flag in ServerRead)"
```

---

### Task 8: Engine-aware database query API

**Files:**
- Modify: `backend/app/api/v1/databases.py`
- Create: `backend/tests/test_databases_api.py`

**Interfaces:**
- Consumes: `server.engine` to dispatch query
- `sql: str` payload is repurposed: SQL for pg/pgvector/mysql; JSON string for mongodb/qdrant
- Returns: same `QueryResponse(columns, rows, row_count, error, status)` for all engines

MongoDB JSON protocol: `{"op": "find"|"count"|"list_collections", "coll": "name", "filter": {}, "limit": 100}`
Qdrant JSON protocol: `{"op": "list"|"info"|"scroll", "coll": "name", "limit": 10}`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_databases_api.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_mysql_query_dispatched_via_aiomysql():
    """Engine=mysql should use aiomysql, not asyncpg."""
    from app.api.v1.databases import _run_mysql_query
    mock_conn = AsyncMock()
    mock_conn.fetchall.return_value = [(1, "alice")]
    mock_conn.description = (("id", None), ("name", None))
    result = await _run_mysql_query(mock_conn, "SELECT id, name FROM users")
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "alice"]]
    assert result.row_count == 1


@pytest.mark.asyncio
async def test_mongodb_find_query():
    """Engine=mongodb with op=find returns rows from motor cursor."""
    from app.api.v1.databases import _run_mongodb_query
    import json
    docs = [{"_id": "abc", "name": "Alice"}, {"_id": "def", "name": "Bob"}]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    mock_col = MagicMock()
    mock_col.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_client = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    payload = json.dumps({"op": "find", "coll": "users", "filter": {}, "limit": 100})
    result = await _run_mongodb_query(mock_client, payload)
    assert result.row_count == 2
    assert "_id" in result.columns or "name" in result.columns


@pytest.mark.asyncio
async def test_mongodb_list_collections():
    from app.api.v1.databases import _run_mongodb_query
    import json
    mock_db = MagicMock()
    mock_db.list_collection_names = AsyncMock(return_value=["users", "orders"])
    mock_client = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    payload = json.dumps({"op": "list_collections"})
    result = await _run_mongodb_query(mock_client, payload)
    assert result.row_count == 2
    assert "collection" in result.columns


@pytest.mark.asyncio
async def test_qdrant_list_query():
    from app.api.v1.databases import _run_qdrant_query
    import httpx, json
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"collections": [{"name": "a"}, {"name": "b"}]}}
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = mock_response
    payload = json.dumps({"op": "list"})
    with patch("app.api.v1.databases.httpx.AsyncClient", return_value=mock_client):
        result = await _run_qdrant_query("http://localhost:6333", None, payload)
    assert result.row_count == 2
    assert "collection" in result.columns
```

- [ ] **Step 2: Run tests — expect FAIL**

```
cd backend && python -m pytest tests/test_databases_api.py -v
```
Expected: FAIL — helper functions don't exist yet

- [ ] **Step 3: Implement engine-aware databases.py**

Replace `backend/app/api/v1/databases.py` with the full implementation:

```python
import json
import logging
import re
from typing import Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user
from app.models.creation_log import CreationLog
from app.models.job import Job
from app.models.server import Server
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/databases", tags=["databases"])

_SELECT_RE = re.compile(r"^\s*(SELECT|WITH|TABLE|VALUES|EXPLAIN|SHOW)\b", re.IGNORECASE)
MAX_ROWS = 500


def _to_json(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    error: Optional[str] = None
    status: Optional[str] = None


async def _run_pg_query(dsn: str, sql: str) -> QueryResponse:
    try:
        conn = await asyncpg.connect(dsn, timeout=10)
    except Exception:
        logger.exception("Failed to connect (pg)")
        return QueryResponse(columns=[], rows=[], row_count=0, error="Cannot connect to database")
    try:
        if _SELECT_RE.match(sql):
            records = await conn.fetch(sql)
            if not records:
                return QueryResponse(columns=[], rows=[], row_count=0)
            columns = list(records[0].keys())
            rows = [[_to_json(v) for v in r.values()] for r in records[:MAX_ROWS]]
            return QueryResponse(columns=columns, rows=rows, row_count=len(records))
        else:
            status = await conn.execute(sql)
            return QueryResponse(columns=["result"], rows=[[status]], row_count=1, status=status)
    except asyncpg.PostgresError as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))
    except Exception:
        logger.exception("PG query failed")
        return QueryResponse(columns=[], rows=[], row_count=0, error="Query execution failed")
    finally:
        await conn.close()


async def _run_mysql_query(conn, sql: str) -> QueryResponse:
    try:
        await conn.execute(sql)
        if conn.description:
            columns = [d[0] for d in conn.description]
            rows_raw = await conn.fetchall()
            rows = [[_to_json(v) for v in row] for row in rows_raw[:MAX_ROWS]]
            return QueryResponse(columns=columns, rows=rows, row_count=len(rows_raw))
        else:
            status = f"Query OK, {conn.rowcount} row(s) affected"
            return QueryResponse(columns=["result"], rows=[[status]], row_count=1, status=status)
    except Exception as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))


async def _run_mongodb_query(client, payload_str: str) -> QueryResponse:
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        return QueryResponse(columns=[], rows=[], row_count=0,
                             error=f"Invalid JSON: {exc}. Format: {{\"op\":\"find\",\"coll\":\"name\",\"filter\":{{}}}}")
    op = payload.get("op", "find")
    db_name = payload.get("db")  # optional; defaults to the provisioned DB
    coll_name = payload.get("coll", "")
    try:
        if op == "list_collections":
            db = client[db_name] if db_name else list(client.list_database_names())[0]
            # db_name should always come from the log — caller provides it
            names = await client[db_name].list_collection_names() if db_name else []
            rows = [[n] for n in names]
            return QueryResponse(columns=["collection"], rows=rows, row_count=len(rows))
        elif op == "find":
            filt = payload.get("filter", {})
            limit = min(int(payload.get("limit", 100)), MAX_ROWS)
            cursor = client[db_name][coll_name].find(filt)
            docs = await cursor.to_list(length=limit)
            if not docs:
                return QueryResponse(columns=[], rows=[], row_count=0)
            columns = list(docs[0].keys())
            rows = [[_to_json(doc.get(c)) for c in columns] for doc in docs]
            return QueryResponse(columns=columns, rows=rows, row_count=len(docs))
        elif op == "count":
            filt = payload.get("filter", {})
            count = await client[db_name][coll_name].count_documents(filt)
            return QueryResponse(columns=["count"], rows=[[count]], row_count=1)
        else:
            return QueryResponse(columns=[], rows=[], row_count=0, error=f"Unknown op: {op!r}. Use: find, count, list_collections")
    except Exception as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))


async def _run_qdrant_query(base_url: str, api_key: Optional[str], payload_str: str) -> QueryResponse:
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        return QueryResponse(columns=[], rows=[], row_count=0,
                             error=f"Invalid JSON: {exc}. Format: {{\"op\":\"list\"}} or {{\"op\":\"info\",\"coll\":\"name\"}}")
    op = payload.get("op", "list")
    coll = payload.get("coll", "")
    headers: dict[str, str] = {}
    if api_key:
        headers["api-key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if op == "list":
                r = await client.get(f"{base_url}/collections", headers=headers)
                collections = r.json().get("result", {}).get("collections", [])
                rows = [[c["name"]] for c in collections]
                return QueryResponse(columns=["collection"], rows=rows, row_count=len(rows))
            elif op == "info":
                r = await client.get(f"{base_url}/collections/{coll}", headers=headers)
                info = r.json().get("result", {})
                rows = [[k, str(v)] for k, v in info.items()]
                return QueryResponse(columns=["key", "value"], rows=rows, row_count=len(rows))
            elif op == "scroll":
                limit = min(int(payload.get("limit", 10)), MAX_ROWS)
                r = await client.post(
                    f"{base_url}/collections/{coll}/points/scroll",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"limit": limit, "with_payload": True},
                )
                points = r.json().get("result", {}).get("points", [])
                if not points:
                    return QueryResponse(columns=[], rows=[], row_count=0)
                columns = ["id"] + list(points[0].get("payload", {}).keys())
                rows = [[p["id"]] + [_to_json(p.get("payload", {}).get(c)) for c in columns[1:]] for p in points]
                return QueryResponse(columns=columns, rows=rows, row_count=len(points))
            else:
                return QueryResponse(columns=[], rows=[], row_count=0, error=f"Unknown op: {op!r}. Use: list, info, scroll")
    except Exception as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))


@router.post("/{log_id}/query", response_model=QueryResponse)
async def query_database(
    log_id: int,
    payload: QueryRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    log = await session.get(CreationLog, log_id)
    if not log or log.is_deleted:
        raise HTTPException(status_code=404, detail="Database not found")

    job = await session.get(Job, log.job_id)
    if not current_user.is_admin and (job is None or job.owner != current_user.username):
        raise HTTPException(status_code=403, detail="Not authorised to query this database")

    server = await session.get(Server, log.server_id)
    if not server or not server.admin_dsn:
        raise HTTPException(status_code=400, detail="Server has no admin DSN — set it in Servers before querying")

    engine = server.engine

    if engine in ("postgresql", "pgvector"):
        db_dsn = server.admin_dsn.rsplit("/", 1)[0] + f"/{log.db_name}"
        return await _run_pg_query(db_dsn, payload.sql)

    elif engine == "mysql":
        import aiomysql
        from urllib.parse import urlparse
        parsed = urlparse(server.admin_dsn)
        try:
            conn = await aiomysql.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 3306,
                user=parsed.username or "root",
                password=parsed.password or "",
                db=log.db_name,
                autocommit=True,
            )
        except Exception:
            logger.exception("Failed to connect (mysql) for log_id=%d", log_id)
            return QueryResponse(columns=[], rows=[], row_count=0, error="Cannot connect to MySQL database")
        try:
            return await _run_mysql_query(conn, payload.sql)
        finally:
            conn.close()

    elif engine == "mongodb":
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(server.admin_dsn, serverSelectionTimeoutMS=5000)
        try:
            payload_with_db = payload.sql
            # Inject db_name so _run_mongodb_query can use it
            try:
                d = json.loads(payload.sql)
                d.setdefault("db", log.db_name)
                payload_with_db = json.dumps(d)
            except json.JSONDecodeError:
                pass
            return await _run_mongodb_query(client, payload_with_db)
        finally:
            client.close()

    elif engine == "qdrant":
        api_key = getattr(server, "api_key", None)
        return await _run_qdrant_query(server.admin_dsn, api_key, payload.sql)

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported engine for console: {engine!r}")
```

- [ ] **Step 4: Run tests**

```
cd backend && python -m pytest tests/test_databases_api.py -v
```
Expected: All PASS

- [ ] **Step 5: Run full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/databases.py backend/tests/test_databases_api.py
git commit -m "feat: engine-aware DB console endpoint (pg/pgvector/mysql/mongodb/qdrant)"
```

---

### Task 9: Server UI — engine dropdown + api_key field

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/pages/Servers.tsx`

**Interfaces:**
- Consumes: `ServerCreate.api_key?: string` (Task 7)
- Produces: engine dropdown (5 options), dynamic port default, dynamic DSN placeholder, api_key field for Qdrant

- [ ] **Step 1: Update types.ts**

In `frontend/src/types.ts`, add `api_key?: string` to `ServerCreate`:

```typescript
export interface ServerCreate {
  name: string
  host: string
  port: number
  engine: string
  environment: string
  region?: string
  max_connections: number
  max_storage_gb: number
  warning_threshold_pct: number
  critical_threshold_pct: number
  admin_dsn?: string
  api_key?: string
}
```

Also add `has_api_key: boolean` to `Server`:

```typescript
export interface Server {
  id: number
  name: string
  host: string
  port: number
  engine: string
  environment: string
  region: string | null
  is_active: boolean
  max_connections: number
  max_storage_gb: number
  warning_threshold_pct: number
  critical_threshold_pct: number
  has_admin_dsn: boolean
  has_api_key: boolean
  created_at: string
  is_deleted: boolean
}
```

- [ ] **Step 2: Update Servers.tsx**

Replace `frontend/src/pages/Servers.tsx` with the full implementation:

```typescript
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Server, ServerCreate } from '../types'

const ENVS = ['development', 'staging', 'production']
const ENGINES = ['postgresql', 'pgvector', 'mysql', 'mongodb', 'qdrant']

const ENGINE_PORT: Record<string, number> = {
  postgresql: 5432, pgvector: 5432, mysql: 3306, mongodb: 27017, qdrant: 6333,
}

const ENGINE_DSN_PLACEHOLDER: Record<string, string> = {
  postgresql: 'postgresql://postgres:pass@host:5432/postgres',
  pgvector:   'postgresql://postgres:pass@host:5432/postgres',
  mysql:      'mysql://root:pass@host:3306/',
  mongodb:    'mongodb://admin:pass@host:27017/',
  qdrant:     'http://host:6333',
}

const ENGINE_DSN_LABEL: Record<string, string> = {
  qdrant: 'Connection URL (no credentials in URL for Qdrant)',
}

const blank: ServerCreate = {
  name: '', host: '', port: 5432, engine: 'postgresql',
  environment: 'development', region: '', max_connections: 100, max_storage_gb: 100,
  warning_threshold_pct: 75, critical_threshold_pct: 90,
}

export default function Servers() {
  const [servers, setServers] = useState<Server[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<ServerCreate>(blank)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    api.servers.list()
      .then(data => setServers(data.filter(s => !s.is_deleted)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const set = (k: keyof ServerCreate, v: string | number) =>
    setForm(f => ({ ...f, [k]: v }))

  const onEngineChange = (engine: string) => {
    setForm(f => ({ ...f, engine, port: ENGINE_PORT[engine] ?? f.port }))
  }

  const openEdit = (s: Server) => {
    setEditingId(s.id)
    setForm({
      name: s.name, host: s.host, port: s.port, engine: s.engine,
      environment: s.environment, region: s.region ?? '',
      max_connections: s.max_connections, max_storage_gb: s.max_storage_gb,
      warning_threshold_pct: s.warning_threshold_pct, critical_threshold_pct: s.critical_threshold_pct,
    })
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  const closeForm = () => {
    setShowForm(false); setEditingId(null); setForm(blank); setError(''); setSuccess('')
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const payload = { ...form, region: form.region || undefined }
      if (editingId !== null) {
        if (!payload.admin_dsn) delete payload.admin_dsn
        if (!payload.api_key) delete payload.api_key
        await api.servers.update(editingId, payload)
        setSuccess('Server updated.')
      } else {
        await api.servers.create(payload)
        setSuccess('Server registered.')
      }
      closeForm()
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete server "${name}"?`)) return
    try {
      await api.servers.remove(id)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const isQdrant = form.engine === 'qdrant'
  const dsnLabel = ENGINE_DSN_LABEL[form.engine] ?? 'Admin DSN'
  const dsnPlaceholder = editingId !== null
    ? 'Leave blank to keep current'
    : ENGINE_DSN_PLACEHOLDER[form.engine] ?? 'connection-string'

  return (
    <>
      <div className="row between mb-4">
        <h2 className="page-title" style={{ marginBottom: 0 }}>Servers</h2>
        <button className="btn btn-primary" onClick={() => showForm ? closeForm() : setShowForm(true)}>
          {showForm ? 'Cancel' : '+ Add Server'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card mb-4">
          <div className="section-title mb-4" style={{ marginBottom: 16 }}>
            {editingId !== null ? 'Edit Server' : 'Register Server'}
          </div>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="prod-pg-01" />
              </div>
              <div className="form-group">
                <label>Engine</label>
                <select value={form.engine} onChange={e => onEngineChange(e.target.value)}>
                  {ENGINES.map(eng => <option key={eng}>{eng}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Host *</label>
                <input required value={form.host} onChange={e => set('host', e.target.value)} placeholder="db.example.com" />
              </div>
              <div className="form-group">
                <label>Port</label>
                <input type="number" value={form.port} onChange={e => set('port', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Environment *</label>
                <select value={form.environment} onChange={e => set('environment', e.target.value)}>
                  {ENVS.map(e => <option key={e}>{e}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Region</label>
                <input value={form.region ?? ''} onChange={e => set('region', e.target.value)} placeholder="us-east-1" />
              </div>
              <div className="form-group">
                <label>Max Connections</label>
                <input type="number" value={form.max_connections} onChange={e => set('max_connections', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Max Storage (GB)</label>
                <input type="number" value={form.max_storage_gb} onChange={e => set('max_storage_gb', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Warning threshold %</label>
                <input type="number" min={0} max={100} value={form.warning_threshold_pct} onChange={e => set('warning_threshold_pct', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Critical threshold %</label>
                <input type="number" min={0} max={100} value={form.critical_threshold_pct} onChange={e => set('critical_threshold_pct', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>
                  {dsnLabel}
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}> (required for provisioning)</span>
                </label>
                <input
                  type="password"
                  value={form.admin_dsn ?? ''}
                  onChange={e => set('admin_dsn', e.target.value)}
                  placeholder={dsnPlaceholder}
                />
              </div>
              {isQdrant && (
                <div className="form-group">
                  <label>
                    API Key
                    <span style={{ color: 'var(--muted)', fontSize: 11 }}> (optional — OSS Qdrant)</span>
                  </label>
                  <input
                    type="password"
                    value={form.api_key ?? ''}
                    onChange={e => set('api_key', e.target.value)}
                    placeholder={editingId !== null ? 'Leave blank to keep current' : 'qdrant-api-key'}
                  />
                </div>
              )}
            </div>
            <div className="row gap-2 mt-4">
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting
                  ? (editingId !== null ? 'Saving…' : 'Registering…')
                  : (editingId !== null ? 'Save Changes' : 'Register Server')}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading servers…</div>
      ) : servers.length === 0 ? (
        <div className="empty">No servers registered yet.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Engine</th>
                <th>Host</th>
                <th>Environment</th>
                <th>Region</th>
                <th>Status</th>
                <th>Admin DSN</th>
                <th>Max Conn</th>
                <th>Warn / Crit %</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {servers.map(s => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500 }}>{s.name}</td>
                  <td><span className="badge badge-inactive" style={{ fontSize: 11 }}>{s.engine}</span></td>
                  <td><code>{s.host}:{s.port}</code></td>
                  <td>{s.environment}</td>
                  <td>{s.region ?? '—'}</td>
                  <td>
                    <span className={`badge badge-${s.is_active ? 'active' : 'inactive'}`}>
                      {s.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: s.has_admin_dsn ? 'var(--green)' : 'var(--muted)', fontSize: 12 }}>
                      {s.has_admin_dsn ? 'Set' : 'Not set'}
                      {s.engine === 'qdrant' && s.has_api_key ? ' · key ✓' : ''}
                    </span>
                  </td>
                  <td>{s.max_connections}</td>
                  <td style={{ fontSize: 12 }}>{s.warning_threshold_pct}% / {s.critical_threshold_pct}%</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-sm" style={{ marginRight: 6 }} onClick={() => openEdit(s)}>Edit</button>
                    <button className="btn btn-danger btn-sm" onClick={() => remove(s.id, s.name)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 3: Manual verification**

Start the dev stack and navigate to Servers page:
```bash
docker compose up -d
# Then open http://localhost:5173/servers
```

Verify:
1. Click "+ Add Server" → form shows Engine dropdown with 5 options
2. Select "mysql" → Port auto-changes to 3306, Admin DSN placeholder shows `mysql://root:pass@host:3306/`
3. Select "qdrant" → Port changes to 6333, DSN placeholder shows `http://host:6333`, API Key field appears
4. Select "postgresql" → API Key field disappears
5. Edit an existing server → form pre-fills correctly

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/pages/Servers.tsx
git commit -m "feat: Server UI — engine dropdown, dynamic port/DSN, Qdrant api_key field"
```

---

### Task 10: Engine-aware DB Console frontend

**Files:**
- Modify: `frontend/src/pages/Jobs.tsx`

**Interfaces:**
- Consumes: `server.engine` from `servers` list prop (looked up by `log.server_id`)
- Produces: engine-appropriate INSPECT and TEMPLATES button sets, placeholder text

- [ ] **Step 1: Manual verification baseline**

Before modifying, confirm the current console works:
```bash
# Open http://localhost:5173
# Submit a provisioning job on a PostgreSQL server, wait for success
# Open History tab, click "Console" on the succeeded entry
# Verify INSPECT and TEMPLATES buttons appear and work
```

- [ ] **Step 2: Update Jobs.tsx**

In `frontend/src/pages/Jobs.tsx`, replace the `INSPECT`, `TEMPLATES` constants and `DbConsole` component with the engine-aware version:

Remove the current top-level `INSPECT` and `TEMPLATES` constants (lines 220-236).

Add engine-specific constants before `DbConsole`:

```typescript
const PG_INSPECT = [
  { label: 'List tables',  sql: "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name" },
  { label: 'List columns', sql: "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position" },
  { label: 'Row counts',   sql: "SELECT relname AS table, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC" },
  { label: 'List indexes', sql: "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname" },
  { label: 'Constraints',  sql: "SELECT tc.table_name, tc.constraint_name, tc.constraint_type, kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu USING (constraint_name, table_schema) WHERE tc.table_schema = 'public' ORDER BY tc.table_name" },
]
const PG_TEMPLATES = [
  { label: 'CREATE TABLE', sql: "CREATE TABLE example (\n  id      SERIAL PRIMARY KEY,\n  name    TEXT NOT NULL,\n  created_at TIMESTAMP DEFAULT NOW()\n);" },
  { label: 'SELECT',       sql: "SELECT * FROM example\nLIMIT 100;" },
  { label: 'INSERT',       sql: "INSERT INTO example (name)\nVALUES ('hello');" },
  { label: 'UPDATE',       sql: "UPDATE example\nSET name = 'world'\nWHERE id = 1;" },
  { label: 'DELETE',       sql: "DELETE FROM example\nWHERE id = 1;" },
  { label: 'ALTER',        sql: "ALTER TABLE example\n  ADD COLUMN email TEXT;" },
  { label: 'DROP TABLE',   sql: "DROP TABLE example;" },
]
const PGVECTOR_TEMPLATES = [
  ...PG_TEMPLATES,
  { label: 'CREATE vector table', sql: "CREATE TABLE embeddings (\n  id      SERIAL PRIMARY KEY,\n  content TEXT,\n  embedding vector(1536)\n);" },
  { label: 'Vector search',       sql: "SELECT id, content,\n       embedding <-> '[0.1,0.2,...]'::vector AS distance\nFROM embeddings\nORDER BY distance\nLIMIT 10;" },
  { label: 'Create HNSW index',   sql: "CREATE INDEX ON embeddings\n  USING hnsw (embedding vector_cosine_ops);" },
]

const MYSQL_INSPECT = [
  { label: 'List tables',   sql: 'SHOW TABLES;' },
  { label: 'List columns',  sql: 'SHOW COLUMNS FROM example;' },
  { label: 'Table info',    sql: 'SHOW CREATE TABLE example;' },
  { label: 'Table sizes',   sql: "SELECT table_name, ROUND((data_length + index_length)/1024/1024,2) AS size_mb FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY size_mb DESC;" },
  { label: 'Active queries', sql: 'SHOW PROCESSLIST;' },
]
const MYSQL_TEMPLATES = [
  { label: 'CREATE TABLE', sql: "CREATE TABLE example (\n  id   INT AUTO_INCREMENT PRIMARY KEY,\n  name VARCHAR(255) NOT NULL,\n  created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n);" },
  { label: 'SELECT',       sql: "SELECT * FROM example\nLIMIT 100;" },
  { label: 'INSERT',       sql: "INSERT INTO example (name)\nVALUES ('hello');" },
  { label: 'UPDATE',       sql: "UPDATE example\nSET name = 'world'\nWHERE id = 1;" },
  { label: 'DELETE',       sql: "DELETE FROM example\nWHERE id = 1;" },
  { label: 'ALTER',        sql: "ALTER TABLE example\n  ADD COLUMN email VARCHAR(255);" },
  { label: 'DROP TABLE',   sql: "DROP TABLE example;" },
]

const MONGO_INSPECT = [
  { label: 'List collections', sql: JSON.stringify({ op: 'list_collections' }, null, 0) },
  { label: 'Count docs',       sql: JSON.stringify({ op: 'count', coll: 'mycol', filter: {} }, null, 0) },
]
const MONGO_TEMPLATES = [
  { label: 'Find all',    sql: JSON.stringify({ op: 'find', coll: 'mycol', filter: {}, limit: 100 }, null, 2) },
  { label: 'Find filter', sql: JSON.stringify({ op: 'find', coll: 'mycol', filter: { status: 'active' }, limit: 50 }, null, 2) },
  { label: 'Count',       sql: JSON.stringify({ op: 'count', coll: 'mycol', filter: {} }, null, 2) },
]

const QDRANT_INSPECT = [
  { label: 'List collections', sql: JSON.stringify({ op: 'list' }, null, 0) },
  { label: 'Collection info',  sql: JSON.stringify({ op: 'info', coll: 'mycol' }, null, 0) },
]
const QDRANT_TEMPLATES = [
  { label: 'List',   sql: JSON.stringify({ op: 'list' }, null, 2) },
  { label: 'Info',   sql: JSON.stringify({ op: 'info', coll: 'mycol' }, null, 2) },
  { label: 'Scroll', sql: JSON.stringify({ op: 'scroll', coll: 'mycol', limit: 10 }, null, 2) },
]

const ENGINE_PLACEHOLDER: Record<string, string> = {
  postgresql: 'SELECT * FROM my_table;  — Ctrl+Enter to run',
  pgvector:   'SELECT * FROM embeddings LIMIT 10;  — Ctrl+Enter to run',
  mysql:      'SELECT * FROM my_table;  — Ctrl+Enter to run',
  mongodb:    '{"op":"find","coll":"users","filter":{},"limit":100}  — Ctrl+Enter to run',
  qdrant:     '{"op":"list"}  — Ctrl+Enter to run',
}

function _inspectTemplates(engine: string): { label: string; sql: string }[] {
  switch (engine) {
    case 'pgvector': return PG_INSPECT
    case 'mysql':    return MYSQL_INSPECT
    case 'mongodb':  return MONGO_INSPECT
    case 'qdrant':   return QDRANT_INSPECT
    default:         return PG_INSPECT
  }
}

function _queryTemplates(engine: string): { label: string; sql: string }[] {
  switch (engine) {
    case 'pgvector': return PGVECTOR_TEMPLATES
    case 'mysql':    return MYSQL_TEMPLATES
    case 'mongodb':  return MONGO_TEMPLATES
    case 'qdrant':   return QDRANT_TEMPLATES
    default:         return PG_TEMPLATES
  }
}
```

Then update the `DbConsole` component signature and body to accept and use engine:

```typescript
function DbConsole({ log, servers, onClose }: { log: CreationLog; servers: Server[]; onClose: () => void }) {
  const server = servers.find(s => s.id === log.server_id)
  const engine = server?.engine ?? 'postgresql'
  const [sql, setSql] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [running, setRunning] = useState(false)

  const run = async (query = sql) => {
    if (!query.trim()) return
    setRunning(true)
    setResult(null)
    try {
      const r = await api.databases.query(log.id, query.trim())
      setResult(r)
    } catch (e: unknown) {
      setResult({ columns: [], rows: [], row_count: 0, error: e instanceof Error ? e.message : String(e), status: null })
    } finally {
      setRunning(false)
    }
  }

  const INSPECT = _inspectTemplates(engine)
  const TEMPLATES = _queryTemplates(engine)
  const placeholder = ENGINE_PLACEHOLDER[engine] ?? 'Enter query — Ctrl+Enter to run'

  return (
    <div className="card mt-6" style={{ marginTop: 24 }}>
      <div className="row between" style={{ marginBottom: 12 }}>
        <div>
          <span className="section-title" style={{ marginRight: 8 }}>Console</span>
          <code style={{ fontSize: 13 }}>{log.db_name}</code>
          <span style={{ color: 'var(--muted)', fontSize: 12, marginLeft: 8 }}>
            {server?.name ?? `server #${log.server_id}`}
          </span>
          <span style={{ color: 'var(--muted)', fontSize: 11, marginLeft: 6 }}>({engine})</span>
        </div>
        <button className="btn btn-sm" onClick={onClose}>✕ Close</button>
      </div>

      <div style={{ marginBottom: 8 }}>
        <div className="row gap-2" style={{ flexWrap: 'wrap', alignItems: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Inspect</span>
          {INSPECT.map(q => (
            <button key={q.label} className="btn btn-secondary btn-sm" onClick={() => { setSql(q.sql); run(q.sql) }}>
              {q.label}
            </button>
          ))}
        </div>
        <div className="row gap-2" style={{ flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Templates</span>
          {TEMPLATES.map(q => (
            <button key={q.label} className="btn btn-sm" onClick={() => setSql(q.sql)}>
              {q.label}
            </button>
          ))}
        </div>
      </div>

      <textarea
        value={sql}
        onChange={e => setSql(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run() }}
        placeholder={placeholder}
        style={{ width: '100%', minHeight: 80, fontFamily: 'monospace', fontSize: 13,
                 background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)',
                 borderRadius: 4, padding: 8, resize: 'vertical', boxSizing: 'border-box' }}
      />
      <div className="row gap-2 mt-2" style={{ marginTop: 8 }}>
        <button className="btn btn-primary btn-sm" onClick={() => run()} disabled={running}>
          {running ? 'Running…' : '▶ Run'}
        </button>
        {result && !result.error && (
          <span style={{ fontSize: 12, color: 'var(--muted)', alignSelf: 'center' }}>
            {result.status ?? `${result.row_count} row${result.row_count !== 1 ? 's' : ''}`}
          </span>
        )}
      </div>

      {result && (
        <div style={{ marginTop: 12 }}>
          {result.error ? (
            <div className="alert alert-error" style={{ fontFamily: 'monospace', fontSize: 12 }}>{result.error}</div>
          ) : result.columns.length === 0 ? (
            <div style={{ color: 'var(--muted)', fontSize: 13 }}>No rows returned.</div>
          ) : (
            <div className="table-wrap" style={{ maxHeight: 400, overflowY: 'auto' }}>
              <table style={{ fontSize: 12 }}>
                <thead>
                  <tr>{result.columns.map(c => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i}>{row.map((v, j) => (
                      <td key={j} style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {v === null ? <span style={{ color: 'var(--muted)' }}>NULL</span> : String(v)}
                      </td>
                    ))}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Manual verification**

```bash
# Ensure dev stack is running
docker compose up -d
# Open http://localhost:5173
```

Verify:
1. Open Jobs → History → Console for a PostgreSQL DB → PostgreSQL INSPECT/TEMPLATES appear
2. If a MySQL server exists: console shows MySQL INSPECT (SHOW TABLES, etc.)
3. Engine label "(postgresql)" appears in console header next to server name
4. MongoDB console shows JSON-format templates
5. Qdrant console shows `{"op":"list"}` format
6. Ctrl+Enter runs the query

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Jobs.tsx
git commit -m "feat: engine-aware DB console (pg/pgvector/mysql/mongodb/qdrant templates)"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|---|---|
| `options: dict` on DatabaseSpec | Task 1 |
| `get_provisioner(server)` factory | Task 1 |
| pgvector subclass of PostgreSQL | Task 2 |
| pgvector always enables `vector` | Task 2 |
| MySQL provisioner (aiomysql) | Task 3 |
| MongoDB provisioner (motor) | Task 4 |
| Qdrant provisioner (httpx) | Task 5 |
| tasks.py uses factory | Task 6 |
| servers.py capacity uses factory | Task 6 |
| `_build_connection_uri` per engine | Task 6 |
| `api_key` on Server model | Task 7 |
| `has_api_key` in ServerRead | Task 7 |
| Alembic migration | Task 7 |
| Engine-aware console endpoint | Task 8 |
| MySQL query (aiomysql) | Task 8 |
| MongoDB query (motor) | Task 8 |
| Qdrant query (httpx) | Task 8 |
| Engine dropdown in Server UI | Task 9 |
| Dynamic port on engine change | Task 9 |
| Dynamic DSN placeholder | Task 9 |
| api_key field for Qdrant UI | Task 9 |
| Engine-specific INSPECT buttons | Task 10 |
| Engine-specific TEMPLATES | Task 10 |
| pgvector vector search templates | Task 10 |

**No placeholders found.**

**Type consistency check:** `get_provisioner(server) -> DatabaseProvisioner` used consistently across Task 1 (definition), Task 6 (tasks.py, servers.py), Task 8 (databases.py does not use factory — uses server.engine directly, which is correct). `_build_connection_uri` defined in Task 6, tested in Task 6. `_run_pg_query`, `_run_mysql_query`, `_run_mongodb_query`, `_run_qdrant_query` defined and tested in Task 8 — no cross-task naming conflicts.

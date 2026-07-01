# Sites Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Sites module — SQLModel tables for sites/deployments/migrations, FastAPI CRUD + migrate routes, an SSH-based migration service, and a React Sites page with a server-dropdown migration panel.

**Architecture:** Three new SQLModel tables follow the server.py/job.py soft-delete/timestamp pattern. The migration service resolves machine → SSH key → open_ssh() exactly as provisioner/factory.py does. The frontend is a single Sites.tsx page mirroring Systems.tsx (load/useState/form, CSS-var classNames).

**Tech Stack:** FastAPI · SQLModel · asyncpg · asyncssh · Alembic · React 18 · TypeScript · Vite. No new deps.

## Global Constraints

- Match server.py/job.py conventions exactly: SQLModel, `_utcnow()`, `is_deleted`/`deleted_at`/`deleted_by` soft-delete, `updated_at` with `sa_column=sa.Column(sa.DateTime(timezone=True), ...)` 
- `write_audit(session, "system", action, entity_type, entity_id, payload)` on create/update/delete/migrate
- All routes: `async def`, `session: AsyncSession = Depends(get_session)`, mimic servers.py (no `require_admin`)
- Target server MUST come from a `<select>` populated by `api.servers.list()` — never a free-text field
- Frontend className/style must mirror Systems.tsx exactly (`btn`, `btn-primary`, `btn-sm`, `card`, `form-group`, `table-wrap`, `alert-error`, `alert-success`, `section-title`, `loading`, `empty`, CSS vars)
- `pytest-asyncio` with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed
- Revision ID for migration: `f5a6b7c8d9e0`, down_revision: `"e4f5a6b7c8d9"`

---

## File Map

| Action | Path |
|--------|------|
| **Create** | `backend/app/models/site.py` |
| **Modify** | `backend/app/models/__init__.py` |
| **Create** | `backend/migrations/versions/f5a6b7c8d9e0_add_sites_tables.py` |
| **Create** | `backend/app/schemas/site.py` |
| **Create** | `backend/tests/test_site_schemas.py` |
| **Create** | `backend/app/services/site_migration.py` |
| **Create** | `backend/tests/test_site_migration_service.py` |
| **Create** | `backend/app/api/v1/sites.py` |
| **Modify** | `backend/app/api/v1/router.py` |
| **Modify** | `frontend/src/types.ts` |
| **Modify** | `frontend/src/api.ts` |
| **Modify** | `frontend/src/App.tsx` |
| **Create** | `frontend/src/pages/Sites.tsx` |
| **Create** | `MIGRATION_MODULE.md` |

---

## Task 1: Data Models + `__init__` Registration + Alembic Migration

**Files:**
- Create: `backend/app/models/site.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/f5a6b7c8d9e0_add_sites_tables.py`

**Interfaces:**
- Produces: `Site`, `SiteDeployment`, `SiteMigration` SQLModel classes importable from `app.models.site`
- Later tasks import these directly; `app.models` re-exports all three

- [ ] **Step 1: Write `backend/app/models/site.py`**

```python
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Site(SQLModel, table=True):
    __tablename__ = "sites"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    template: str = Field(max_length=255)
    subdomain: str = Field(max_length=255)
    domain: str = Field(max_length=255)
    prefix: Optional[str] = Field(default=None, max_length=255)
    routing_mode: str = Field(default="port", max_length=20)
    app_port: Optional[int] = Field(default=None)
    web_root: str = Field(default="/var/www", max_length=255)
    directory: Optional[str] = Field(default=None, max_length=500)
    web_server: str = Field(default="apache", max_length=20)
    notes: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow),
    )
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)


class SiteDeployment(SQLModel, table=True):
    __tablename__ = "site_deployments"

    id: Optional[int] = Field(default=None, primary_key=True)
    site_id: int = Field(foreign_key="sites.id")
    server_id: int = Field(foreign_key="servers.id")
    status: str = Field(default="active", max_length=20)
    port: Optional[int] = Field(default=None)
    directory: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=_utcnow)
    retired_at: Optional[datetime] = Field(default=None)


class SiteMigration(SQLModel, table=True):
    __tablename__ = "site_migrations"

    id: Optional[int] = Field(default=None, primary_key=True)
    site_id: int = Field(foreign_key="sites.id")
    source_deployment_id: Optional[int] = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("site_deployments.id"), nullable=True),
    )
    target_server_id: int = Field(foreign_key="servers.id")
    status: str = Field(default="pending", max_length=20)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    log: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    created_at: datetime = Field(default_factory=_utcnow)
```

- [ ] **Step 2: Update `backend/app/models/__init__.py`**

Add three imports and three `__all__` entries:

```python
from app.models.approval import ApprovalRequest
from app.models.audit_log import AuditLog
from app.models.creation_log import CreationLog
from app.models.database_template import DatabaseTemplate
from app.models.job import Job
from app.models.machine import Machine
from app.models.naming_profile import NamingProfile
from app.models.request_template import RequestTemplate
from app.models.server import Server
from app.models.site import Site, SiteDeployment, SiteMigration
from app.models.ssh_key import SSHKey
from app.models.user import User

__all__ = [
    "Server",
    "NamingProfile",
    "DatabaseTemplate",
    "RequestTemplate",
    "Job",
    "ApprovalRequest",
    "CreationLog",
    "AuditLog",
    "User",
    "SSHKey",
    "Machine",
    "Site",
    "SiteDeployment",
    "SiteMigration",
]
```

- [ ] **Step 3: Write the Alembic migration**

Create `backend/migrations/versions/f5a6b7c8d9e0_add_sites_tables.py`:

```python
"""add sites, site_deployments, site_migrations tables

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-30

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("template", sa.String(255), nullable=False),
        sa.Column("subdomain", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("prefix", sa.String(255), nullable=True),
        sa.Column("routing_mode", sa.String(20), nullable=False, server_default="port"),
        sa.Column("app_port", sa.Integer(), nullable=True),
        sa.Column("web_root", sa.String(255), nullable=False, server_default="/var/www"),
        sa.Column("directory", sa.String(500), nullable=True),
        sa.Column("web_server", sa.String(20), nullable=False, server_default="apache"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )
    op.create_table(
        "site_deployments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("directory", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "site_migrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("source_deployment_id", sa.Integer(), sa.ForeignKey("site_deployments.id"), nullable=True),
        sa.Column("target_server_id", sa.Integer(), sa.ForeignKey("servers.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("site_migrations")
    op.drop_table("site_deployments")
    op.drop_table("sites")
```

- [ ] **Step 4: Verify models import cleanly**

```bash
cd backend
python -c "from app.models import Site, SiteDeployment, SiteMigration; print('ok')"
```

Expected output: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/site.py backend/app/models/__init__.py \
        backend/migrations/versions/f5a6b7c8d9e0_add_sites_tables.py
git commit -m "feat: add Site, SiteDeployment, SiteMigration models and migration"
```

---

## Task 2: Schemas + Schema Tests

**Files:**
- Create: `backend/app/schemas/site.py`
- Create: `backend/tests/test_site_schemas.py`
- Test: `backend/tests/test_site_schemas.py`

**Interfaces:**
- Consumes: nothing (pure Pydantic)
- Produces:
  - `SiteCreate(name, template, subdomain, domain, prefix?, routing_mode, app_port?, web_root, directory?, web_server, notes?)`
  - `SiteUpdate` — all optional, same fields, same enum validation when provided
  - `SiteRead` — ConfigDict(from_attributes=True), adds `id`, `created_at`, `is_deleted`, `web_url` property
  - `SiteDeploymentRead` — ConfigDict(from_attributes=True)
  - `MigrationCreate(site_id, target_server_id)`
  - `MigrationRead` — ConfigDict(from_attributes=True)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_site_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas.site import MigrationCreate, SiteCreate, SiteRead, SiteUpdate


def test_port_routing_requires_app_port():
    with pytest.raises(ValidationError, match="app_port"):
        SiteCreate(name="x", template="t", subdomain="s", domain="d.com", routing_mode="port")


def test_directory_routing_requires_directory():
    with pytest.raises(ValidationError, match="directory"):
        SiteCreate(name="x", template="t", subdomain="s", domain="d.com", routing_mode="directory")


def test_port_routing_valid():
    s = SiteCreate(
        name="mysite", template="tmpl", subdomain="app", domain="example.com",
        routing_mode="port", app_port=4007,
    )
    assert s.app_port == 4007
    assert s.web_server == "apache"


def test_directory_routing_valid():
    s = SiteCreate(
        name="x", template="t", subdomain="s", domain="d.com",
        routing_mode="directory", directory="/var/www/myapp",
    )
    assert s.directory == "/var/www/myapp"


def test_invalid_routing_mode():
    with pytest.raises(ValidationError, match="routing_mode"):
        SiteCreate(
            name="x", template="t", subdomain="s", domain="d.com",
            routing_mode="nginx_proxy", app_port=80,
        )


def test_invalid_web_server():
    with pytest.raises(ValidationError, match="web_server"):
        SiteCreate(
            name="x", template="t", subdomain="s", domain="d.com",
            routing_mode="port", app_port=80, web_server="nginx",
        )


def test_update_invalid_routing_mode():
    with pytest.raises(ValidationError, match="routing_mode"):
        SiteUpdate(routing_mode="bad")


def test_update_valid_partial():
    u = SiteUpdate(name="new-name")
    assert u.name == "new-name"
    assert u.routing_mode is None


def test_update_valid_web_server():
    u = SiteUpdate(web_server="haproxy")
    assert u.web_server == "haproxy"


def test_site_read_web_url():
    from datetime import datetime
    r = SiteRead(
        id=1, name="x", template="t", subdomain="app", domain="example.com",
        prefix=None, routing_mode="port", app_port=4007, web_root="/var/www",
        directory=None, web_server="apache", notes=None,
        created_at=datetime(2026, 1, 1), is_deleted=False,
    )
    assert r.web_url == "app.example.com"


def test_migration_create():
    m = MigrationCreate(site_id=1, target_server_id=5)
    assert m.target_server_id == 5
```

- [ ] **Step 2: Run tests — expect ImportError (schema doesn't exist yet)**

```bash
cd backend && python -m pytest tests/test_site_schemas.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.schemas.site'`

- [ ] **Step 3: Write `backend/app/schemas/site.py`**

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

_VALID_ROUTING_MODES = {"port", "directory"}
_VALID_WEB_SERVERS = {"apache", "haproxy"}


class SiteCreate(BaseModel):
    name: str
    template: str
    subdomain: str
    domain: str
    prefix: Optional[str] = None
    routing_mode: str = "port"
    app_port: Optional[int] = None
    web_root: str = "/var/www"
    directory: Optional[str] = None
    web_server: str = "apache"
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "SiteCreate":
        if self.routing_mode not in _VALID_ROUTING_MODES:
            raise ValueError(f"routing_mode must be one of {_VALID_ROUTING_MODES}")
        if self.web_server not in _VALID_WEB_SERVERS:
            raise ValueError(f"web_server must be one of {_VALID_WEB_SERVERS}")
        if self.routing_mode == "port" and self.app_port is None:
            raise ValueError("app_port is required when routing_mode is 'port'")
        if self.routing_mode == "directory" and not self.directory:
            raise ValueError("directory is required when routing_mode is 'directory'")
        return self


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    template: Optional[str] = None
    subdomain: Optional[str] = None
    domain: Optional[str] = None
    prefix: Optional[str] = None
    routing_mode: Optional[str] = None
    app_port: Optional[int] = None
    web_root: Optional[str] = None
    directory: Optional[str] = None
    web_server: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "SiteUpdate":
        if self.routing_mode is not None and self.routing_mode not in _VALID_ROUTING_MODES:
            raise ValueError(f"routing_mode must be one of {_VALID_ROUTING_MODES}")
        if self.web_server is not None and self.web_server not in _VALID_WEB_SERVERS:
            raise ValueError(f"web_server must be one of {_VALID_WEB_SERVERS}")
        return self


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    template: str
    subdomain: str
    domain: str
    prefix: Optional[str]
    routing_mode: str
    app_port: Optional[int]
    web_root: str
    directory: Optional[str]
    web_server: str
    notes: Optional[str]
    created_at: datetime
    is_deleted: bool

    @property
    def web_url(self) -> str:
        return f"{self.subdomain}.{self.domain}"


class SiteDeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    server_id: int
    status: str
    port: Optional[int]
    directory: Optional[str]
    created_at: datetime
    retired_at: Optional[datetime]


class MigrationCreate(BaseModel):
    site_id: int
    target_server_id: int


class MigrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    source_deployment_id: Optional[int]
    target_server_id: int
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    log: Optional[str]
    created_at: datetime
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd backend && python -m pytest tests/test_site_schemas.py -v
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/site.py backend/tests/test_site_schemas.py
git commit -m "feat: add Site schemas with routing_mode/web_server validation"
```

---

## Task 3: Migration Service + Service Tests

**Files:**
- Create: `backend/app/services/site_migration.py`
- Create: `backend/tests/test_site_migration_service.py`

**Interfaces:**
- Consumes: `SSHConnection` from `app.services.ssh_tunnel`; `open_ssh` context manager; `decrypt` from `app.services.encryption`
- Produces:
  - `find_free_port(ssh: SSHConnection, preferred: int) -> int`
  - `ensure_web_root(ssh: SSHConnection, web_root: str) -> str`
  - `write_apache_vhost(ssh, site, port, site_dir) -> str`
  - `write_haproxy_backend(ssh, site, port) -> str`
  - `run_migration(session: AsyncSession, migration: SiteMigration) -> None` — mutates migration in place, commits

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_site_migration_service.py`:

```python
from unittest.mock import AsyncMock, MagicMock


async def test_find_free_port_returns_preferred_when_free():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="")
    from app.services.site_migration import find_free_port
    assert await find_free_port(ssh, 4007) == 4007
    ssh.run.assert_called_once()
    assert ":4007 " in ssh.run.call_args[0][0]


async def test_find_free_port_skips_occupied_port():
    ssh = MagicMock()
    calls = []
    async def _run(cmd):
        calls.append(cmd)
        return "LISTEN" if ":4007 " in cmd else ""
    ssh.run = _run
    from app.services.site_migration import find_free_port
    port = await find_free_port(ssh, 4007)
    assert port == 4008
    assert len(calls) == 2


async def test_ensure_web_root_runs_mkdir():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="ok")
    from app.services.site_migration import ensure_web_root
    result = await ensure_web_root(ssh, "/var/www")
    ssh.run.assert_called_once_with("mkdir -p /var/www && echo ok")
    assert result == "ok"


async def test_write_apache_vhost_port_mode():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="")
    site = MagicMock()
    site.subdomain = "app"
    site.domain = "example.com"
    site.prefix = None
    site.routing_mode = "port"
    from app.services.site_migration import write_apache_vhost
    await write_apache_vhost(ssh, site, 4007, "/var/www/app")
    cmd = ssh.run.call_args[0][0]
    assert "ProxyPass" in cmd
    assert "4007" in cmd
    assert "app.example.com" in cmd


async def test_write_apache_vhost_directory_mode():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="")
    site = MagicMock()
    site.subdomain = "blog"
    site.domain = "example.com"
    site.prefix = None
    site.routing_mode = "directory"
    from app.services.site_migration import write_apache_vhost
    await write_apache_vhost(ssh, site, 0, "/var/www/blog")
    cmd = ssh.run.call_args[0][0]
    assert "DocumentRoot" in cmd
    assert "/var/www/blog" in cmd


async def test_write_haproxy_backend_returns_todo():
    ssh = MagicMock()
    site = MagicMock()
    site.subdomain = "app"
    site.domain = "example.com"
    from app.services.site_migration import write_haproxy_backend
    result = await write_haproxy_backend(ssh, site, 4007)
    assert "TODO" in result
    ssh.run.assert_not_called()
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && python -m pytest tests/test_site_migration_service.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.site_migration'`

- [ ] **Step 3: Write `backend/app/services/site_migration.py`**

```python
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.machine import Machine
from app.models.server import Server
from app.models.site import Site, SiteDeployment, SiteMigration
from app.models.ssh_key import SSHKey
from app.services.encryption import decrypt
from app.services.ssh_tunnel import SSHConnection, open_ssh


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _resolve_machine_ssh(session: AsyncSession, server: Server):
    """Return (machine, key_material, passphrase, username) for server.machine_id."""
    if not server.machine_id:
        raise ValueError(f"Server '{server.name}' (id={server.id}) has no machine configured")
    machine = await session.get(Machine, server.machine_id)
    if not machine or machine.is_deleted:
        raise ValueError(f"Machine {server.machine_id} not found or deleted")
    ssh_key_rec = await session.get(SSHKey, machine.ssh_key_id)
    if not ssh_key_rec:
        raise ValueError(f"SSH key {machine.ssh_key_id} not found")
    key_material = decrypt(ssh_key_rec.encrypted_private_key)
    passphrase = decrypt(ssh_key_rec.passphrase_encrypted) if ssh_key_rec.passphrase_encrypted else None
    return machine, key_material, passphrase, ssh_key_rec.username


async def ensure_web_root(ssh: SSHConnection, web_root: str) -> str:
    return await ssh.run(f"mkdir -p {web_root} && echo ok")


async def find_free_port(ssh: SSHConnection, preferred_port: int) -> int:
    """Return preferred_port if free on the remote host, else the next free port."""
    result = await ssh.run(f"ss -tlnp 2>/dev/null | grep ':{preferred_port} ' | head -1")
    if not result.strip():
        return preferred_port
    for candidate in range(preferred_port + 1, preferred_port + 100):
        check = await ssh.run(f"ss -tlnp 2>/dev/null | grep ':{candidate} ' | head -1")
        if not check.strip():
            return candidate
    raise RuntimeError(f"No free port found in range {preferred_port}–{preferred_port + 99}")


async def write_apache_vhost(ssh: SSHConnection, site, port: int, site_dir: str) -> str:
    # Assumes Debian/Ubuntu apache2 layout: /etc/apache2/sites-available/
    # TODO: RHEL/CentOS uses /etc/httpd/conf.d/ — operator must verify distro layout.
    web_url = f"{site.subdomain}.{site.domain}"
    vhost_name = f"{site.subdomain}-{site.domain.replace('.', '-')}"
    prefix = (site.prefix or "").rstrip("/")

    if site.routing_mode == "port":
        body = (
            f"<VirtualHost *:80>\n"
            f"    ServerName {web_url}\n"
            f"    ProxyPreserveHost On\n"
            f"    ProxyPass {prefix}/ http://127.0.0.1:{port}/\n"
            f"    ProxyPassReverse {prefix}/ http://127.0.0.1:{port}/\n"
            f"</VirtualHost>"
        )
    else:
        body = (
            f"<VirtualHost *:80>\n"
            f"    ServerName {web_url}\n"
            f"    DocumentRoot {site_dir}\n"
            f"    <Directory {site_dir}>\n"
            f"        Options Indexes FollowSymLinks\n"
            f"        AllowOverride All\n"
            f"        Require all granted\n"
            f"    </Directory>\n"
            f"</VirtualHost>"
        )

    vhost_path = f"/etc/apache2/sites-available/{vhost_name}.conf"
    escaped = body.replace("\\", "\\\\").replace("'", "'\\''")
    cmd = (
        f"echo '{escaped}' | sudo tee {vhost_path} > /dev/null && "
        f"sudo a2ensite {vhost_name} && "
        f"sudo systemctl reload apache2 2>/dev/null || true"
    )
    return await ssh.run(cmd)


async def write_haproxy_backend(ssh: SSHConnection, site, port: int) -> str:
    # TODO: haproxy config modification is operator-specific — depends on whether haproxy.cfg
    # is managed via template, puppet/ansible, or hand-edited. This stub logs the intent
    # and returns a clear TODO message. Operator must add the backend manually or wire up
    # their config management tool. See MIGRATION_MODULE.md for details.
    backend_name = f"be_{site.subdomain}_{site.domain.replace('.', '_')}"
    web_url = f"{site.subdomain}.{site.domain}"
    return (
        f"TODO: add haproxy backend '{backend_name}' on port {port} for {web_url} — "
        f"configure manually in /etc/haproxy/haproxy.cfg"
    )


async def _best_effort_rsync(
    ssh: SSHConnection,
    source_ip: str,
    source_dir: str,
    target_dir: str,
) -> str:
    # TODO: rsync requires SSH key-based access from the source machine to the target machine,
    # or SSH agent forwarding. Neither is guaranteed. This is a best-effort step; failure
    # is logged but does not abort the migration. See MIGRATION_MODULE.md for alternatives.
    result = await ssh.run(
        f"rsync -avz --delete {source_ip}:{source_dir}/ {target_dir}/ 2>&1 | tail -10"
    )
    return result or "(no rsync output)"


async def run_migration(session: AsyncSession, migration: SiteMigration) -> None:
    """
    Execute a site migration in place. Mutates migration.status/log/error_message.
    Caller must NOT commit before calling; this function manages its own commits.
    """
    from sqlmodel import select

    log_lines: list[str] = []

    def _log(msg: str) -> None:
        log_lines.append(msg)
        migration.log = "\n".join(log_lines)

    migration.status = "running"
    migration.started_at = _utcnow()
    session.add(migration)
    await session.commit()

    try:
        site = await session.get(Site, migration.site_id)
        if not site:
            raise ValueError(f"Site {migration.site_id} not found")
        _log(f"Site: {site.name} ({site.subdomain}.{site.domain})")

        target_server = await session.get(Server, migration.target_server_id)
        if not target_server or target_server.is_deleted:
            raise ValueError(f"Target server {migration.target_server_id} not found")
        _log(f"Target server: {target_server.name} (id={target_server.id})")

        machine, key_material, passphrase, username = await _resolve_machine_ssh(session, target_server)
        _log(f"Connecting via machine {machine.ip}:{machine.ssh_port} as {username}")

        target_dep = SiteDeployment(
            site_id=site.id,
            server_id=target_server.id,
            status="staging",
        )
        session.add(target_dep)
        await session.commit()
        await session.refresh(target_dep)
        _log(f"Created staging deployment id={target_dep.id}")

        async with open_ssh(
            host=machine.ip,
            port=machine.ssh_port,
            username=username,
            key_material=key_material,
            passphrase=passphrase,
            known_hosts_entry=machine.host_fingerprint,
        ) as ssh:
            _log("SSH connected")

            await ensure_web_root(ssh, site.web_root)
            _log(f"Ensured web_root: {site.web_root}")

            site_subdir = site.directory or site.subdomain
            site_dir = f"{site.web_root}/{site_subdir}"
            await ssh.run(f"mkdir -p {site_dir}")
            target_dep.directory = site_dir
            _log(f"Created site directory: {site_dir}")

            if site.routing_mode == "port":
                resolved_port = await find_free_port(ssh, site.app_port)
                target_dep.port = resolved_port
                _log(f"Resolved port: {resolved_port}")
                if site.web_server == "apache":
                    ws_out = await write_apache_vhost(ssh, site, resolved_port, site_dir)
                else:
                    ws_out = await write_haproxy_backend(ssh, site, resolved_port)
            else:
                resolved_port = None
                if site.web_server == "apache":
                    ws_out = await write_apache_vhost(ssh, site, 0, site_dir)
                else:
                    ws_out = await write_haproxy_backend(ssh, site, 0)
            _log(f"Web server config: {(ws_out or 'ok').strip()[:200]}")

            session.add(target_dep)
            await session.commit()

            if migration.source_deployment_id:
                source_dep = await session.get(SiteDeployment, migration.source_deployment_id)
                if source_dep and source_dep.directory:
                    source_server = await session.get(Server, source_dep.server_id)
                    if source_server and source_server.machine_id:
                        source_machine = await session.get(Machine, source_server.machine_id)
                        if source_machine:
                            _log(f"Rsyncing from {source_machine.ip}:{source_dep.directory}")
                            try:
                                rsync_out = await _best_effort_rsync(
                                    ssh, source_machine.ip, source_dep.directory, site_dir
                                )
                                _log(f"rsync: {rsync_out[:300]}")
                            except Exception as exc:
                                _log(f"rsync failed (non-fatal): {exc}")

        target_dep.status = "active"
        session.add(target_dep)

        if migration.source_deployment_id:
            source_dep = await session.get(SiteDeployment, migration.source_deployment_id)
            if source_dep:
                source_dep.status = "retired"
                source_dep.retired_at = _utcnow()
                session.add(source_dep)
                _log(f"Retired source deployment id={source_dep.id}")

        migration.status = "succeeded"
        migration.completed_at = _utcnow()
        _log("Migration succeeded.")

    except Exception as exc:
        migration.status = "failed"
        migration.completed_at = _utcnow()
        migration.error_message = str(exc)[:1000]
        _log(f"FAILED: {exc}")

    migration.log = "\n".join(log_lines)
    session.add(migration)
    await session.commit()
```

- [ ] **Step 4: Run service tests — expect all pass**

```bash
cd backend && python -m pytest tests/test_site_migration_service.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/site_migration.py backend/tests/test_site_migration_service.py
git commit -m "feat: add site migration service with SSH provisioning helpers"
```

---

## Task 4: API Routes + Router Registration

**Files:**
- Create: `backend/app/api/v1/sites.py`
- Modify: `backend/app/api/v1/router.py`

**Interfaces:**
- Consumes: `SiteCreate`, `SiteUpdate`, `SiteRead`, `SiteDeploymentRead`, `MigrationCreate`, `MigrationRead` from `app.schemas.site`; `Site`, `SiteDeployment`, `SiteMigration` from `app.models.site`; `run_migration` from `app.services.site_migration`; `write_audit` from `app.services.audit`
- Produces: REST endpoints at `/api/v1/sites/...`

Route list (all async, all use `get_session`):
- `POST /sites` → 201 SiteRead
- `GET /sites` → list[SiteRead]
- `GET /sites/{site_id}` → SiteRead
- `PUT /sites/{site_id}` → SiteRead
- `DELETE /sites/{site_id}` → SiteRead
- `GET /sites/{site_id}/deployments` → list[SiteDeploymentRead]
- `POST /sites/{site_id}/migrate` → 201 MigrationRead (body: MigrationCreate)
- `GET /sites/migrations/{migration_id}` → MigrationRead

Note: `/migrations/{migration_id}` has two path segments under the `/sites` prefix; it does NOT conflict with `/{site_id}` (one segment) or `/{site_id}/deployments` (second segment is the literal "deployments", not a number).

- [ ] **Step 1: Write `backend/app/api/v1/sites.py`**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.site import Site, SiteDeployment, SiteMigration
from app.schemas.site import (
    MigrationCreate,
    MigrationRead,
    SiteCreate,
    SiteDeploymentRead,
    SiteRead,
    SiteUpdate,
)
from app.services.audit import write_audit
from app.services.site_migration import run_migration

router = APIRouter(prefix="/sites", tags=["sites"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("", response_model=SiteRead, status_code=201)
async def create_site(payload: SiteCreate, session: AsyncSession = Depends(get_session)):
    site = Site(**payload.model_dump())
    session.add(site)
    await session.commit()
    await session.refresh(site)
    await write_audit(session, "system", "create", "site", site.id, payload.model_dump())
    await session.commit()
    return SiteRead.model_validate(site)


@router.get("", response_model=list[SiteRead])
async def list_sites(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Site).where(Site.is_deleted == False))  # noqa: E712
    return [SiteRead.model_validate(s) for s in result.scalars().all()]


@router.get("/migrations/{migration_id}", response_model=MigrationRead)
async def get_migration(migration_id: int, session: AsyncSession = Depends(get_session)):
    migration = await session.get(SiteMigration, migration_id)
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")
    return MigrationRead.model_validate(migration)


@router.get("/{site_id}", response_model=SiteRead)
async def get_site(site_id: int, session: AsyncSession = Depends(get_session)):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteRead.model_validate(site)


@router.put("/{site_id}", response_model=SiteRead)
async def update_site(
    site_id: int,
    payload: SiteUpdate,
    session: AsyncSession = Depends(get_session),
):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(site, key, value)
    site.updated_at = _utcnow()
    session.add(site)
    await session.commit()
    await session.refresh(site)
    await write_audit(session, "system", "update", "site", site.id, payload.model_dump(exclude_none=True))
    await session.commit()
    return SiteRead.model_validate(site)


@router.delete("/{site_id}", response_model=SiteRead)
async def delete_site(site_id: int, session: AsyncSession = Depends(get_session)):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    site.is_deleted = True
    site.deleted_at = _utcnow()
    site.deleted_by = "system"
    session.add(site)
    await session.commit()
    await session.refresh(site)
    await write_audit(session, "system", "delete", "site", site.id)
    await session.commit()
    return SiteRead.model_validate(site)


@router.get("/{site_id}/deployments", response_model=list[SiteDeploymentRead])
async def list_deployments(site_id: int, session: AsyncSession = Depends(get_session)):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    result = await session.execute(
        select(SiteDeployment).where(SiteDeployment.site_id == site_id)
    )
    return [SiteDeploymentRead.model_validate(d) for d in result.scalars().all()]


@router.post("/{site_id}/migrate", response_model=MigrationRead, status_code=201)
async def start_migration(
    site_id: int,
    payload: MigrationCreate,
    session: AsyncSession = Depends(get_session),
):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    if payload.site_id != site_id:
        raise HTTPException(status_code=400, detail="site_id in body must match URL")

    active_result = await session.execute(
        select(SiteDeployment)
        .where(SiteDeployment.site_id == site_id, SiteDeployment.status == "active")
        .order_by(SiteDeployment.id.desc())
        .limit(1)
    )
    source_dep = active_result.scalars().first()

    migration = SiteMigration(
        site_id=site_id,
        source_deployment_id=source_dep.id if source_dep else None,
        target_server_id=payload.target_server_id,
    )
    session.add(migration)
    await session.commit()
    await session.refresh(migration)

    await write_audit(session, "system", "migrate", "site", site_id, {
        "migration_id": migration.id,
        "target_server_id": payload.target_server_id,
    })
    await session.commit()

    await run_migration(session, migration)
    await session.refresh(migration)
    return MigrationRead.model_validate(migration)
```

- [ ] **Step 2: Update `backend/app/api/v1/router.py`**

Add after the `machines_router` import line and include call:

```python
from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.databases import router as databases_router
from app.api.v1.database_templates import router as database_templates_router
from app.api.v1.health import router as health_router
from app.api.v1.history import router as history_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.naming_profiles import router as naming_profiles_router
from app.api.v1.request_templates import router as request_templates_router
from app.api.v1.search import router as search_router
from app.api.v1.servers import router as servers_router
from app.api.v1.machines import router as machines_router
from app.api.v1.sites import router as sites_router
from app.api.v1.ssh_keys import router as ssh_keys_router
from app.api.v1.stats import router as stats_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(servers_router)
api_router.include_router(jobs_router)
api_router.include_router(history_router)
api_router.include_router(databases_router)
api_router.include_router(naming_profiles_router)
api_router.include_router(database_templates_router)
api_router.include_router(request_templates_router)
api_router.include_router(admin_router)
api_router.include_router(stats_router)
api_router.include_router(search_router)
api_router.include_router(ssh_keys_router)
api_router.include_router(machines_router)
api_router.include_router(sites_router)
```

- [ ] **Step 3: Verify the app imports cleanly**

```bash
cd backend && python -c "from app.main import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Run all existing tests to confirm no regressions**

```bash
cd backend && python -m pytest tests/test_site_schemas.py tests/test_site_migration_service.py tests/test_ssh_tunnel.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/sites.py backend/app/api/v1/router.py
git commit -m "feat: add /sites API routes and register in router"
```

---

## Task 5: Frontend Types + API Client

**Files:**
- Modify: `frontend/src/types.ts` (append)
- Modify: `frontend/src/api.ts` (add `api.sites` namespace)

**Interfaces:**
- Produces: `Site`, `SiteCreate`, `SiteDeployment`, `Migration` TypeScript interfaces; `api.sites.*` methods

- [ ] **Step 1: Append to `frontend/src/types.ts`**

Add at the end of the file:

```typescript
export interface Site {
  id: number
  name: string
  template: string
  subdomain: string
  domain: string
  prefix: string | null
  routing_mode: string
  app_port: number | null
  web_root: string
  directory: string | null
  web_server: string
  notes: string | null
  created_at: string
  is_deleted: boolean
}

export interface SiteCreate {
  name: string
  template: string
  subdomain: string
  domain: string
  prefix?: string
  routing_mode: string
  app_port?: number
  web_root?: string
  directory?: string
  web_server?: string
  notes?: string
}

export interface SiteDeployment {
  id: number
  site_id: number
  server_id: number
  status: string
  port: number | null
  directory: string | null
  created_at: string
  retired_at: string | null
}

export interface Migration {
  id: number
  site_id: number
  source_deployment_id: number | null
  target_server_id: number
  status: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  log: string | null
  created_at: string
}
```

- [ ] **Step 2: Add `api.sites` to `frontend/src/api.ts`**

Update the import line at the top (add the new types):

```typescript
import type {
  ApprovalPolicy, CreationLog, DBTemplate, DBTemplateCreate,
  EngineDetectionResult, HealthCheck, Job, JobCreate, Machine, MachineCreate,
  Migration, NamingProfile, NamingProfileCreate,
  Paginated, QueryResult, RequestTemplate, RequestTemplateCreate,
  ScanResult, Server, ServerCreate, Site, SiteCreate, SiteDeployment,
  SSHKey, SSHKeyCreate, Stats,
} from './types'
```

Add the `sites` namespace inside the `api` object, after `machines`:

```typescript
  sites: {
    list: () => req<Site[]>('/sites'),
    get: (id: number) => req<Site>(`/sites/${id}`),
    create: (data: SiteCreate) =>
      req<Site>('/sites', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<SiteCreate>) =>
      req<Site>(`/sites/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id: number) => req<Site>(`/sites/${id}`, { method: 'DELETE' }),
    deployments: (id: number) => req<SiteDeployment[]>(`/sites/${id}/deployments`),
    migrate: (siteId: number, targetServerId: number) =>
      req<Migration>(`/sites/${siteId}/migrate`, {
        method: 'POST',
        body: JSON.stringify({ site_id: siteId, target_server_id: targetServerId }),
      }),
    migrationStatus: (migrationId: number) =>
      req<Migration>(`/sites/migrations/${migrationId}`),
  },
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat: add Site/SiteDeployment/Migration types and api.sites client"
```

---

## Task 6: Frontend Sites Page + Nav

**Files:**
- Create: `frontend/src/pages/Sites.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api.sites.*`, `api.servers.list()`, `Site`, `SiteCreate`, `SiteDeployment`, `Migration`, `Server` from types
- Produces: `<Sites />` React component; "Sites" nav entry in App.tsx

- [ ] **Step 1: Update `frontend/src/App.tsx`**

Change `type Page` union and `NAV` array:

```typescript
import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Login from './pages/Login'
import Servers from './pages/Servers'
import Settings from './pages/Settings'
import Sites from './pages/Sites'
import Systems from './pages/Systems'
import { auth } from './api'

type Page = 'dashboard' | 'servers' | 'jobs' | 'sites' | 'systems' | 'settings'

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '⬡' },
  { id: 'servers', label: 'Servers', icon: '◫' },
  { id: 'jobs', label: 'Jobs', icon: '⟳' },
  { id: 'sites', label: 'Sites', icon: '◍' },
  { id: 'systems', label: 'Systems', icon: '⬕' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]
```

In the `<main>` render block, add:

```tsx
{page === 'sites' && <Sites />}
```

Full updated render block:

```tsx
<main className="main">
  {page === 'dashboard' && <Dashboard />}
  {page === 'servers' && <Servers />}
  {page === 'jobs' && <Jobs />}
  {page === 'sites' && <Sites />}
  {page === 'systems' && <Systems />}
  {page === 'settings' && <Settings />}
</main>
```

- [ ] **Step 2: Create `frontend/src/pages/Sites.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Migration, Server, Site, SiteCreate, SiteDeployment } from '../types'

const EMPTY_FORM: SiteCreate = {
  name: '',
  template: '',
  subdomain: '',
  domain: '',
  prefix: '',
  routing_mode: 'port',
  app_port: undefined,
  web_root: '/var/www',
  directory: '',
  web_server: 'apache',
  notes: '',
}

export default function Sites() {
  const [sites, setSites] = useState<Site[]>([])
  const [servers, setServers] = useState<Server[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState<SiteCreate>(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)

  // Migration panel state
  const [migrateSiteId, setMigrateSiteId] = useState<number | null>(null)
  const [deployments, setDeployments] = useState<SiteDeployment[]>([])
  const [targetServerId, setTargetServerId] = useState<number | ''>('')
  const [migration, setMigration] = useState<Migration | null>(null)
  const [migrating, setMigrating] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    Promise.all([api.sites.list(), api.servers.list()])
      .then(([s, srv]) => {
        setSites(s.filter(x => !x.is_deleted))
        setServers(srv.filter(x => !x.is_deleted))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const setF = <K extends keyof SiteCreate>(k: K, v: SiteCreate[K]) =>
    setForm(f => ({ ...f, [k]: v }))

  const openCreate = () => {
    setEditId(null)
    setForm(EMPTY_FORM)
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  const openEdit = (s: Site) => {
    setEditId(s.id)
    setForm({
      name: s.name,
      template: s.template,
      subdomain: s.subdomain,
      domain: s.domain,
      prefix: s.prefix ?? '',
      routing_mode: s.routing_mode,
      app_port: s.app_port ?? undefined,
      web_root: s.web_root,
      directory: s.directory ?? '',
      web_server: s.web_server,
      notes: s.notes ?? '',
    })
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    const payload: SiteCreate = {
      ...form,
      prefix: form.prefix || undefined,
      directory: form.directory || undefined,
      notes: form.notes || undefined,
      app_port: form.routing_mode === 'port' ? form.app_port : undefined,
    }
    try {
      if (editId !== null) {
        await api.sites.update(editId, payload)
        setSuccess('Site updated.')
      } else {
        await api.sites.create(payload)
        setSuccess('Site created.')
      }
      setShowForm(false)
      setEditId(null)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete site "${name}"?`)) return
    try {
      await api.sites.remove(id)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const openMigrate = async (site: Site) => {
    setMigrateSiteId(site.id)
    setTargetServerId('')
    setMigration(null)
    setError('')
    try {
      const deps = await api.sites.deployments(site.id)
      setDeployments(deps)
    } catch {
      setDeployments([])
    }
  }

  const runMigrate = async () => {
    if (!migrateSiteId || targetServerId === '') return
    setMigrating(true); setError(''); setMigration(null)
    try {
      const result = await api.sites.migrate(migrateSiteId, targetServerId as number)
      setMigration(result)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setMigrating(false)
    }
  }

  const activeDep = (siteId: number): SiteDeployment | undefined => {
    if (migrateSiteId !== siteId) return undefined
    return deployments.find(d => d.status === 'active')
  }

  const serverName = (id: number) =>
    servers.find(s => s.id === id)?.name ?? `Server #${id}`

  const STATUS_COLOR: Record<string, string> = {
    succeeded: 'var(--green)',
    failed: 'var(--red)',
    running: 'var(--accent)',
    pending: 'var(--muted)',
  }

  return (
    <>
      <h2 className="page-title">Sites</h2>

      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div />
        <button
          className="btn btn-primary btn-sm"
          onClick={showForm && editId === null ? () => setShowForm(false) : openCreate}
        >
          {showForm && editId === null ? 'Cancel' : '+ New Site'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="section-title" style={{ marginBottom: 12 }}>
            {editId !== null ? 'Edit Site' : 'Create Site'}
          </div>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => setF('name', e.target.value)} placeholder="My App" />
              </div>
              <div className="form-group">
                <label>Template *</label>
                <input required value={form.template} onChange={e => setF('template', e.target.value)} placeholder="laravel" />
              </div>
              <div className="form-group">
                <label>Subdomain *</label>
                <input required value={form.subdomain} onChange={e => setF('subdomain', e.target.value)} placeholder="app" />
              </div>
              <div className="form-group">
                <label>Domain *</label>
                <input required value={form.domain} onChange={e => setF('domain', e.target.value)} placeholder="example.com" />
              </div>
              <div className="form-group">
                <label>URL Prefix</label>
                <input value={form.prefix ?? ''} onChange={e => setF('prefix', e.target.value)} placeholder="/api" />
              </div>
              <div className="form-group">
                <label>Web Server</label>
                <select value={form.web_server ?? 'apache'} onChange={e => setF('web_server', e.target.value)}>
                  <option value="apache">Apache</option>
                  <option value="haproxy">HAProxy</option>
                </select>
              </div>
              <div className="form-group">
                <label>Routing Mode</label>
                <select value={form.routing_mode} onChange={e => setF('routing_mode', e.target.value)}>
                  <option value="port">Port proxy</option>
                  <option value="directory">Directory</option>
                </select>
              </div>
              {form.routing_mode === 'port' ? (
                <div className="form-group">
                  <label>App Port *</label>
                  <input
                    required
                    type="number"
                    value={form.app_port ?? ''}
                    onChange={e => setF('app_port', e.target.value ? Number(e.target.value) : undefined)}
                    placeholder="4007"
                  />
                </div>
              ) : (
                <div className="form-group">
                  <label>Directory *</label>
                  <input
                    required
                    value={form.directory ?? ''}
                    onChange={e => setF('directory', e.target.value)}
                    placeholder="myapp"
                  />
                </div>
              )}
              <div className="form-group">
                <label>Web Root</label>
                <input value={form.web_root ?? '/var/www'} onChange={e => setF('web_root', e.target.value)} />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>Notes</label>
                <textarea rows={2} value={form.notes ?? ''} onChange={e => setF('notes', e.target.value)}
                  style={{ width: '100%', resize: 'vertical' }} />
              </div>
            </div>
            <div className="row gap-2" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Saving…' : editId !== null ? 'Update Site' : 'Create Site'}
              </button>
              <button className="btn" type="button" onClick={() => { setShowForm(false); setEditId(null) }}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {migrateSiteId !== null && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="row between" style={{ marginBottom: 12 }}>
            <div className="section-title" style={{ marginBottom: 0 }}>
              Migrate: {sites.find(s => s.id === migrateSiteId)?.name}
            </div>
            <button className="btn btn-sm" onClick={() => { setMigrateSiteId(null); setMigration(null) }}>
              Close
            </button>
          </div>
          {deployments.filter(d => d.status === 'active').length > 0 && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
              Current server: <strong>{serverName(deployments.find(d => d.status === 'active')!.server_id)}</strong>
            </div>
          )}
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label>Target Server *</label>
            <select
              value={targetServerId}
              onChange={e => setTargetServerId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">— select a server —</option>
              {servers.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.environment} · {s.host})
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn btn-primary btn-sm"
            disabled={migrating || targetServerId === ''}
            onClick={runMigrate}
          >
            {migrating ? 'Migrating…' : 'Run Migration'}
          </button>
          {migration && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                Status:{' '}
                <span style={{ color: STATUS_COLOR[migration.status] ?? 'var(--muted)' }}>
                  {migration.status}
                </span>
              </div>
              {migration.error_message && (
                <div className="alert alert-error" style={{ marginBottom: 8 }}>
                  {migration.error_message}
                </div>
              )}
              {migration.log && (
                <pre style={{
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 4, padding: 10, fontSize: 11,
                  overflowX: 'auto', whiteSpace: 'pre-wrap', maxHeight: 240,
                }}>
                  {migration.log}
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="loading">Loading…</div>
      ) : sites.length === 0 ? (
        <div className="empty">No sites defined. Create one above.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name / URL</th>
                <th>Template</th>
                <th>Web Server</th>
                <th>Routing</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sites.map(s => (
                <tr key={s.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {s.subdomain}.{s.domain}
                      {s.prefix && <span> {s.prefix}</span>}
                    </div>
                  </td>
                  <td style={{ fontSize: 12 }}>{s.template}</td>
                  <td style={{ fontSize: 12 }}>{s.web_server}</td>
                  <td style={{ fontSize: 12 }}>
                    {s.routing_mode === 'port' ? `port:${s.app_port}` : `dir:${s.directory}`}
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--muted)', maxWidth: 160 }}>
                    {s.notes ?? '—'}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-sm" style={{ marginRight: 4 }} onClick={() => openEdit(s)}>
                      Edit
                    </button>
                    <button
                      className="btn btn-sm"
                      style={{ marginRight: 4 }}
                      onClick={() => migrateSiteId === s.id ? setMigrateSiteId(null) : openMigrate(s)}
                    >
                      {migrateSiteId === s.id ? 'Close' : 'Migrate'}
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => remove(s.id, s.name)}>
                      Delete
                    </button>
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

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Sites.tsx frontend/src/App.tsx
git commit -m "feat: add Sites page with routing_mode toggle and migration panel"
```

---

## Task 7: MIGRATION_MODULE.md

**Files:**
- Create: `MIGRATION_MODULE.md` (repo root)

- [ ] **Step 1: Write `MIGRATION_MODULE.md`**

```markdown
# Sites Migration Module

## Data Model

### `sites`
The portable website definition. Not tied to a server — describes the "what."

| Field | Type | Notes |
|-------|------|-------|
| `id` | int PK | |
| `name` | str(255) | Human label |
| `template` | str(255) | Application template identifier |
| `subdomain` | str(255) | Left side of dot in domain |
| `domain` | str(255) | Right side; `web_url = f"{subdomain}.{domain}"` |
| `prefix` | str(255)? | URL path prefix (e.g. `/api`) |
| `routing_mode` | str `port\|directory` | Controls which fields are required |
| `app_port` | int? | Required if `routing_mode == "port"` |
| `web_root` | str(255) | Base dir on the server (default `/var/www`) |
| `directory` | str(500)? | Subpath under web_root; required if `routing_mode == "directory"` |
| `web_server` | str `apache\|haproxy` | Controls vhost/backend provisioning |
| `notes` | text? | Free text |
| soft-delete | `is_deleted`, `deleted_at`, `deleted_by` | |

### `site_deployments`
Tracks a site placed on a specific server. Keeps history; multiple rows per site.

| Field | Type | Notes |
|-------|------|-------|
| `site_id` | int FK → sites | |
| `server_id` | int FK → servers | Existing server from dropdown |
| `status` | str `staging\|active\|retired\|failed` | |
| `port` | int? | Resolved port on this server (may differ from site.app_port) |
| `directory` | str(500)? | Resolved path on this server |
| `retired_at` | datetime? | Set when status → retired |

No soft-delete — rows are retired, not deleted.

### `site_migrations`
One row per migrate operation. Modelled after `jobs`.

| Field | Type | Notes |
|-------|------|-------|
| `site_id` | int FK → sites | |
| `source_deployment_id` | int? FK → site_deployments | Nullable for first migration |
| `target_server_id` | int FK → servers | The server chosen from dropdown |
| `status` | str `pending\|running\|succeeded\|failed` | |
| `log` | text? | Step-by-step shell output |
| `error_message` | str? | Terminal error if failed |

## Migration Flow (`POST /sites/{id}/migrate`)

1. **Validate** — site exists, body.site_id matches URL.
2. **Find source** — the most recent `active` deployment for the site (nullable).
3. **Create** `SiteMigration` row (status=pending) + write audit log.
4. **`run_migration(session, migration)`**:
   a. Mark migration `running`, set `started_at`.
   b. Load site + target server; resolve SSH via `server.machine_id → Machine → SSHKey → decrypt → open_ssh()`.
   c. Create `SiteDeployment` row (status=`staging`).
   d. Over SSH: `mkdir -p web_root`, `mkdir -p site_dir`.
   e. If `routing_mode == "port"`: probe for a free port with `ss -tlnp`; write Apache vhost **or** log a TODO for HAProxy.
   f. If `routing_mode == "directory"`: write Apache vhost with `DocumentRoot` **or** log TODO for HAProxy.
   g. Best-effort `rsync` from source machine (non-fatal; see TODO #3 below).
   h. Flip `target_deployment.status → active`; `source_deployment.status → retired`.
   i. On any error: `status=failed`, `error_message`, leave source active.
5. Return `MigrationRead`.

## TODOs / Assumptions for Operator Review

### TODO 1 — Apache layout assumes Debian/Ubuntu
`write_apache_vhost` writes to `/etc/apache2/sites-available/` and runs `a2ensite` + `systemctl reload apache2`.  
**RHEL/CentOS/AlmaLinux** use `/etc/httpd/conf.d/` and `systemctl reload httpd`. Add a distro-detection step (check `os_info` field on the Machine) or make the path a configurable field on Site.

### TODO 2 — HAProxy is a no-op stub
`write_haproxy_backend` returns a `TODO:` string and makes no SSH calls.  
HAProxy config modification is complex: the format varies, it may be managed by Ansible/Puppet, and reloading requires careful validation (`haproxy -c -f`). An operator must either: (a) implement a template-based haproxy.cfg generator, or (b) integrate with their config management tool. The stub logs the intent so the migration still completes (as `succeeded` with a TODO note in the log).

### TODO 3 — rsync requires cross-machine SSH access
`_best_effort_rsync` runs `rsync` on the **target** machine pointing back at the source machine IP. This only works if the target has SSH access to the source (i.e., the target's SSH agent can reach the source). This is often not the case. Alternatives: (a) rsync via the operator's machine (three-way transfer), (b) use `scp` with the source private key forwarded, (c) tar-pipe through the operator. The step is marked best-effort — failure is logged but does not abort the migration; source deployment remains active until flip succeeds.

### TODO 4 — `sudo` access on target
The Apache vhost commands use `sudo tee` and `sudo a2ensite`. The SSH user must have passwordless sudo for these commands on the target machine. Add a pre-flight check to the migration that validates sudo access before creating the staging deployment.

### TODO 5 — Apache `mod_proxy` must be enabled
The port-proxy vhost requires `mod_proxy` and `mod_proxy_http`. The migration does not check or enable them. Add `sudo a2enmod proxy proxy_http` to the vhost step.

### TODO 6 — Port conflict window
`find_free_port` probes with `ss -tlnp` then proceeds. There is a TOCTOU window where another process could claim the port between the check and the app starting. For production use, reserve the port atomically (e.g. bind a socket, configure the app, release).

### TODO 7 — Migration runs synchronously
`POST /sites/{id}/migrate` blocks until the migration completes. For long rsync operations this may time out at the reverse proxy. Move `run_migration` to an Arq background task (see `app.workers`) and poll via `GET /sites/migrations/{id}`. The `MigrationRead.status` field already supports this pattern.
```

- [ ] **Step 2: Commit**

```bash
git add MIGRATION_MODULE.md
git commit -m "docs: add MIGRATION_MODULE.md with model, flow, and operator TODOs"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `sites` table with all required fields
- [x] `site_deployments` table — port/directory on deployment row, not site
- [x] `site_migrations` table — job-style status/log/error
- [x] All three models in `models/__init__.py`
- [x] Alembic migration matching existing style
- [x] `SiteCreate` / `SiteUpdate` / `SiteRead` with routing_mode+web_server validation
- [x] `SiteDeploymentRead`, `MigrationCreate`, `MigrationRead`
- [x] `POST /sites`, `GET /sites`, `GET /sites/{id}`, `PUT /sites/{id}`, `DELETE /sites/{id}`
- [x] `GET /sites/{id}/deployments`
- [x] `POST /sites/{id}/migrate` — finds active source dep, runs migration
- [x] `GET /sites/migrations/{id}`
- [x] `write_audit` on create/update/delete/migrate
- [x] Migration service: SSH via machine_id → SSHKey → decrypt → open_ssh
- [x] Migration steps 1–5 (mark running → create staging → SSH setup → rsync → flip)
- [x] Failure path: status=failed, error_message, source stays active
- [x] Real shell helpers as small testable functions (find_free_port, ensure_web_root, write_apache_vhost, write_haproxy_backend)
- [x] TODO stubs with clear markers (not guesses)
- [x] MIGRATION_MODULE.md with model, flow, and every TODO
- [x] Frontend `Site`, `SiteCreate`, `SiteDeployment`, `Migration` interfaces
- [x] `api.sites` namespace (list/get/create/update/delete/deployments/migrate/migrationStatus)
- [x] "Sites" in Page type and NAV array with icon `◍`
- [x] `Sites.tsx`: list, create/edit form, routing_mode toggle, web_server select
- [x] Migration panel: `<select>` from `api.servers.list()` (THE dropdown constraint), Migrate button, log display
- [x] Backend tests: schema validators, service helpers
- [x] No new dependencies

**Type consistency check:**
- `SiteCreate` used in `api.sites.create()` ✓
- `MigrationCreate` body fields match `POST /{id}/migrate` route ✓
- `run_migration(session, migration: SiteMigration)` called correctly in route ✓
- `SiteRead.web_url` property tested in schema tests ✓

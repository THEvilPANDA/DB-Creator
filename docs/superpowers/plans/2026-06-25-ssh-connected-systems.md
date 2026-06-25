# SSH-Connected Systems Fleet Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SSH key management, machine inventory (manual + network scan), and DB provisioning via SSH tunnel to DBCreator.

**Architecture:** Two new DB models (`SSHKey`, `Machine`) with a nullable `machine_id` FK added to `Server`. The provisioner factory becomes an async context manager: when `machine_id` is set it opens an SSH tunnel via `asyncssh` and rewrites the DSN before handing off to the existing provisioner; when unset it behaves exactly as today. Frontend gains a new "Systems" page (SSH Keys + Machines tabs).

**Tech Stack:** Python/FastAPI backend, asyncssh, cryptography (Fernet), React/TypeScript frontend.

## Global Constraints

- Python 3.12+, FastAPI 0.115+, asyncssh (new dep), cryptography 43.0.3 (already installed)
- All SSH key material encrypted with Fernet before storage; never returned by any API endpoint
- Network scan CIDR validation: only RFC-1918 / RFC-4193 private ranges allowed
- Soft-delete pattern (`is_deleted`, `deleted_at`) for Machine records matching Server pattern
- Migration revision chain: current head is `d3e4f5a6b7c8`; new revision is `e4f5a6b7c8d9`
- Frontend follows existing patterns: `api.ts` `req<T>()` helper, `types.ts` interfaces, inline forms in page components
- All backend test files use `pytest-asyncio` with the fixtures in `backend/tests/conftest.py`
- Run backend tests from `backend/` directory: `python -m pytest tests/ -v`

---

### Task 1: Add asyncssh + encryption service

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/encryption.py`
- Create: `backend/tests/test_encryption.py`

**Interfaces:**
- Produces: `encrypt(plaintext: str) -> str`, `decrypt(ciphertext: str) -> str` from `app.services.encryption`

- [ ] **Step 1: Add asyncssh to requirements.txt**

Open `backend/requirements.txt` and add after the last line:
```
asyncssh>=2.18.0
```

- [ ] **Step 2: Install the new dependency**

```bash
cd backend
python -m pip install asyncssh>=2.18.0
```

Expected: installs without error.

- [ ] **Step 3: Write the failing test**

Create `backend/tests/test_encryption.py`:

```python
import pytest
from unittest.mock import patch
from app.services.encryption import encrypt, decrypt


def test_roundtrip():
    key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    with patch("app.services.encryption.settings") as mock_settings:
        # Generate a valid Fernet key for tests
        from cryptography.fernet import Fernet
        real_key = Fernet.generate_key().decode()
        mock_settings.FERNET_KEY = real_key
        ciphertext = encrypt("hello secret")
        assert decrypt(ciphertext) == "hello secret"


def test_no_key_raises():
    with patch("app.services.encryption.settings") as mock_settings:
        mock_settings.FERNET_KEY = ""
        with pytest.raises(RuntimeError, match="FERNET_KEY"):
            encrypt("anything")
```

- [ ] **Step 4: Run to verify it fails**

```bash
cd backend
python -m pytest tests/test_encryption.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `app.services.encryption` does not exist yet.

- [ ] **Step 5: Create the encryption service**

Create `backend/app/services/encryption.py`:

```python
from cryptography.fernet import Fernet
from app.config import settings


def _fernet() -> Fernet:
    if not settings.FERNET_KEY:
        raise RuntimeError("FERNET_KEY is not set — cannot encrypt secrets")
    return Fernet(settings.FERNET_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_encryption.py -v
```

Expected: 2 PASSED.

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/services/encryption.py backend/tests/test_encryption.py
git commit -m "feat: add asyncssh dependency and Fernet encryption service"
```

---

### Task 2: SSHKey + Machine models + migration

**Files:**
- Create: `backend/app/models/ssh_key.py`
- Create: `backend/app/models/machine.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/e4f5a6b7c8d9_add_ssh_keys_machines_server_fk.py`
- Modify: `backend/app/models/server.py`

**Interfaces:**
- Produces: `SSHKey` SQLModel (table=True), `Machine` SQLModel (table=True)
- Produces: `Server.machine_id` optional FK column

- [ ] **Step 1: Create SSHKey model**

Create `backend/app/models/ssh_key.py`:

```python
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SSHKey(SQLModel, table=True):
    __tablename__ = "ssh_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    username: str = Field(max_length=255)
    encrypted_private_key: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    passphrase_encrypted: Optional[str] = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    created_at: datetime = Field(default_factory=_utcnow)
```

- [ ] **Step 2: Create Machine model**

Create `backend/app/models/machine.py`:

```python
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Machine(SQLModel, table=True):
    __tablename__ = "machines"

    id: Optional[int] = Field(default=None, primary_key=True)
    ip: str = Field(max_length=45)
    hostname: Optional[str] = Field(default=None, max_length=255)
    label: Optional[str] = Field(default=None, max_length=255)
    ssh_port: int = Field(default=22)
    ssh_key_id: int = Field(foreign_key="ssh_keys.id")
    os_info: Optional[str] = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    host_fingerprint: Optional[str] = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    status: str = Field(default="unknown", max_length=20)
    last_checked_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
```

- [ ] **Step 3: Add machine_id FK to Server model**

Open `backend/app/models/server.py` and add after the `api_key` line:

```python
    machine_id: Optional[int] = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("machines.id"), nullable=True),
    )
```

- [ ] **Step 4: Register new models in __init__.py**

Open `backend/app/models/__init__.py` and add the two new imports + __all__ entries:

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
]
```

- [ ] **Step 5: Write the migration**

Create `backend/migrations/versions/e4f5a6b7c8d9_add_ssh_keys_machines_server_fk.py`:

```python
"""add ssh_keys, machines tables and machine_id FK on servers

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ssh_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("encrypted_private_key", sa.Text(), nullable=False),
        sa.Column("passphrase_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "machines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("ssh_key_id", sa.Integer(), sa.ForeignKey("ssh_keys.id"), nullable=False),
        sa.Column("os_info", sa.Text(), nullable=True),
        sa.Column("host_fingerprint", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.add_column("servers", sa.Column(
        "machine_id", sa.Integer(), sa.ForeignKey("machines.id"), nullable=True
    ))


def downgrade() -> None:
    op.drop_column("servers", "machine_id")
    op.drop_table("machines")
    op.drop_table("ssh_keys")
```

- [ ] **Step 6: Apply the migration**

```bash
cd backend
alembic upgrade head
```

Expected: migration runs without error, new tables visible in DB.

- [ ] **Step 7: Verify models load in tests**

```bash
cd backend
python -m pytest tests/test_models.py -v
```

Expected: all existing tests still PASS (no regressions from schema change).

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/ssh_key.py backend/app/models/machine.py backend/app/models/server.py backend/app/models/__init__.py backend/migrations/versions/e4f5a6b7c8d9_add_ssh_keys_machines_server_fk.py
git commit -m "feat: add SSHKey and Machine models, migration, machine_id FK on Server"
```

---

### Task 3: SSH key, machine, and server schemas

**Files:**
- Create: `backend/app/schemas/ssh_key.py`
- Create: `backend/app/schemas/machine.py`
- Modify: `backend/app/schemas/server.py`

**Interfaces:**
- Produces: `SSHKeyCreate`, `SSHKeyRead` from `app.schemas.ssh_key`
- Produces: `MachineCreate`, `MachineUpdate`, `MachineRead`, `EngineDetectionResult`, `ScanRequest`, `ScanResult` from `app.schemas.machine`
- Produces: `ServerCreate.machine_id`, `ServerUpdate.machine_id`, `ServerRead.machine_id`

- [ ] **Step 1: Create SSH key schemas**

Create `backend/app/schemas/ssh_key.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SSHKeyCreate(BaseModel):
    name: str
    username: str
    private_key: str
    passphrase: Optional[str] = None


class SSHKeyRead(BaseModel):
    id: int
    name: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Create machine schemas**

Create `backend/app/schemas/machine.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MachineCreate(BaseModel):
    ip: str
    ssh_port: int = 22
    ssh_key_id: int
    label: Optional[str] = None


class MachineUpdate(BaseModel):
    label: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_key_id: Optional[int] = None


class MachineRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    ip: str
    hostname: Optional[str]
    label: Optional[str]
    ssh_port: int
    ssh_key_id: int
    os_info: Optional[str]
    host_fingerprint: Optional[str]
    status: str
    last_checked_at: Optional[datetime]
    created_at: datetime
    is_deleted: bool


class EngineDetectionResult(BaseModel):
    port: int
    engine: str
    open: bool


class ScanRequest(BaseModel):
    cidr: str
    method: str  # "ping" | "port22" | "both"


class ScanResult(BaseModel):
    ip: str
    ping_ok: bool
    ssh_open: bool
```

- [ ] **Step 3: Add machine_id to server schemas**

Open `backend/app/schemas/server.py` and add `machine_id: Optional[int] = None` to `ServerCreate`, `ServerUpdate`, and `ServerRead`:

In `ServerCreate`:
```python
class ServerCreate(BaseModel):
    name: str
    host: str
    port: int = 5432
    engine: str = "postgresql"
    environment: str
    region: Optional[str] = None
    is_active: bool = True
    max_connections: int = 100
    max_storage_gb: float = 100.0
    warning_threshold_pct: float = 75.0
    critical_threshold_pct: float = 90.0
    admin_dsn: Optional[str] = None
    api_key: Optional[str] = None
    machine_id: Optional[int] = None
```

In `ServerUpdate`:
```python
class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    is_active: Optional[bool] = None
    max_connections: Optional[int] = None
    max_storage_gb: Optional[float] = None
    warning_threshold_pct: Optional[float] = None
    critical_threshold_pct: Optional[float] = None
    admin_dsn: Optional[str] = None
    api_key: Optional[str] = None
    machine_id: Optional[int] = None
```

In `ServerRead`, add `machine_id: Optional[int]` and update the `_populate_flags` validator to include it:
```python
class ServerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    port: int
    engine: str
    environment: str
    region: Optional[str]
    is_active: bool
    max_connections: int
    max_storage_gb: float
    warning_threshold_pct: float
    critical_threshold_pct: float
    has_admin_dsn: bool = False
    has_api_key: bool = False
    machine_id: Optional[int] = None
    created_at: datetime
    is_deleted: bool

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

- [ ] **Step 4: Run existing server tests to verify no regression**

```bash
cd backend
python -m pytest tests/api/test_servers.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/ssh_key.py backend/app/schemas/machine.py backend/app/schemas/server.py
git commit -m "feat: add SSHKey and Machine schemas, add machine_id to Server schemas"
```

---

### Task 4: SSH tunnel service

**Files:**
- Create: `backend/app/services/ssh_tunnel.py`
- Create: `backend/tests/test_ssh_tunnel.py`

**Interfaces:**
- Consumes: `asyncssh`, `app.services.encryption.decrypt`
- Produces:
  - `open_ssh(host, port, username, key_material, passphrase?) -> AsyncContextManager[SSHConnection]`
  - `SSHConnection.run(command: str) -> str`
  - `SSHConnection.host_fingerprint() -> str | None`
  - `open_tunnel(host, ssh_port, username, key_material, db_port, passphrase?) -> AsyncContextManager[int]` (yields local_port)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ssh_tunnel.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_open_ssh_connects_with_key():
    mock_conn = MagicMock()
    mock_conn.get_server_host_key.return_value = None

    with patch("app.services.ssh_tunnel.asyncssh.connect", new=AsyncMock(return_value=mock_conn)) as mock_connect, \
         patch("app.services.ssh_tunnel.asyncssh.import_private_key", return_value=MagicMock()) as mock_import:
        from app.services.ssh_tunnel import open_ssh
        async with open_ssh("1.2.3.4", 22, "ubuntu", "FAKE_PEM") as conn:
            assert conn is not None
        mock_connect.assert_called_once()
        mock_import.assert_called_once_with("FAKE_PEM", passphrase=None)
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_open_tunnel_yields_local_port():
    mock_listener = MagicMock()
    mock_conn = MagicMock()
    mock_conn.get_server_host_key.return_value = None
    mock_conn.forward_local_port = AsyncMock(return_value=mock_listener)

    with patch("app.services.ssh_tunnel.asyncssh.connect", new=AsyncMock(return_value=mock_conn)), \
         patch("app.services.ssh_tunnel.asyncssh.import_private_key", return_value=MagicMock()), \
         patch("app.services.ssh_tunnel._find_free_port", return_value=54321):
        from app.services.ssh_tunnel import open_tunnel
        async with open_tunnel("1.2.3.4", 22, "ubuntu", "FAKE_PEM", 5432) as local_port:
            assert local_port == 54321
        mock_listener.close.assert_called_once()
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/test_ssh_tunnel.py -v
```

Expected: `ModuleNotFoundError` — `app.services.ssh_tunnel` does not exist.

- [ ] **Step 3: Create the SSH tunnel service**

Create `backend/app/services/ssh_tunnel.py`:

```python
import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import asyncssh


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class SSHConnection:
    def __init__(self, conn: asyncssh.SSHClientConnection):
        self._conn = conn

    async def run(self, command: str) -> str:
        result = await self._conn.run(command, check=False)
        return result.stdout or ""

    def host_fingerprint(self) -> Optional[str]:
        key = self._conn.get_server_host_key()
        return key.get_fingerprint() if key else None

    async def forward_port(
        self, remote_host: str, remote_port: int
    ) -> tuple[asyncssh.SSHListener, int]:
        local_port = _find_free_port()
        listener = await self._conn.forward_local_port(
            "127.0.0.1", local_port, remote_host, remote_port
        )
        return listener, local_port


@asynccontextmanager
async def open_ssh(
    host: str,
    port: int,
    username: str,
    key_material: str,
    passphrase: Optional[str] = None,
) -> AsyncIterator[SSHConnection]:
    private_key = asyncssh.import_private_key(key_material, passphrase=passphrase)
    conn = await asyncssh.connect(
        host,
        port=port,
        username=username,
        client_keys=[private_key],
        known_hosts=None,
    )
    try:
        yield SSHConnection(conn)
    finally:
        conn.close()


@asynccontextmanager
async def open_tunnel(
    host: str,
    ssh_port: int,
    username: str,
    key_material: str,
    db_port: int,
    passphrase: Optional[str] = None,
) -> AsyncIterator[int]:
    async with open_ssh(host, ssh_port, username, key_material, passphrase) as ssh:
        listener, local_port = await ssh.forward_port(host, db_port)
        try:
            yield local_port
        finally:
            listener.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_ssh_tunnel.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ssh_tunnel.py backend/tests/test_ssh_tunnel.py
git commit -m "feat: add SSH tunnel service (open_ssh, open_tunnel)"
```

---

### Task 5: Network scanner service

**Files:**
- Create: `backend/app/services/network_scanner.py`
- Create: `backend/tests/test_network_scanner.py`

**Interfaces:**
- Produces: `scan(cidr: str, method: str) -> list[dict]` from `app.services.network_scanner`
- Produces: `NetworkScanError(ValueError)` raised on invalid/public CIDR

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_network_scanner.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.network_scanner import scan, NetworkScanError


@pytest.mark.asyncio
async def test_rejects_public_cidr():
    with pytest.raises(NetworkScanError, match="private"):
        await scan("8.8.8.0/24", "port22")


@pytest.mark.asyncio
async def test_rejects_invalid_cidr():
    with pytest.raises(NetworkScanError, match="Invalid"):
        await scan("not-a-cidr", "port22")


@pytest.mark.asyncio
async def test_port22_scan_finds_open_hosts():
    async def fake_open_connection(ip, port, **kwargs):
        if ip == "192.168.1.1":
            mock = MagicMock()
            mock.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock.__aexit__ = AsyncMock(return_value=None)
            reader, writer = MagicMock(), MagicMock()
            writer.close = MagicMock()
            return reader, writer
        raise OSError("refused")

    with patch("asyncio.open_connection", side_effect=fake_open_connection):
        results = await scan("192.168.1.0/30", "port22")

    assert any(r["ip"] == "192.168.1.1" and r["ssh_open"] for r in results)
    assert any(r["ip"] == "192.168.1.2" and not r["ssh_open"] for r in results)
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/test_network_scanner.py -v
```

Expected: `ModuleNotFoundError` — `app.services.network_scanner` does not exist.

- [ ] **Step 3: Create the network scanner**

Create `backend/app/services/network_scanner.py`:

```python
import asyncio
import ipaddress
import platform
from typing import Optional

_PRIVATE_NETWORKS = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv6Network("fc00::/7"),
]

_ENGINE_BY_PORT: dict[int, str] = {
    5432: "postgresql",
    3306: "mysql",
    27017: "mongodb",
    6333: "qdrant",
}

_SCAN_CONCURRENCY = 50


class NetworkScanError(ValueError):
    pass


def _validate_cidr(cidr: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        raise NetworkScanError(f"Invalid CIDR: {cidr!r}")
    for private in _PRIVATE_NETWORKS:
        try:
            if network.subnet_of(private) or network.overlaps(private):
                return network
        except TypeError:
            continue
    raise NetworkScanError(
        f"Only private IP ranges are allowed for scanning (RFC-1918 / RFC-4193). Got: {cidr}"
    )


async def _check_port(ip: str, port: int, sem: asyncio.Semaphore, timeout: float = 1.0) -> bool:
    async with sem:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout
            )
            writer.close()
            return True
        except Exception:
            return False


async def _ping(ip: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        flag = "-n" if platform.system() == "Windows" else "-c"
        proc = await asyncio.create_subprocess_exec(
            "ping", flag, "1", ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0


async def scan(cidr: str, method: str) -> list[dict]:
    network = _validate_cidr(cidr)
    hosts = [str(h) for h in network.hosts()]
    sem = asyncio.Semaphore(_SCAN_CONCURRENCY)

    async def _probe(ip: str) -> dict:
        ping_ok = False
        ssh_open = False
        if method in ("ping", "both"):
            ping_ok = await _ping(ip, sem)
        if method == "port22" or (method == "both" and ping_ok):
            ssh_open = await _check_port(ip, 22, sem)
        return {"ip": ip, "ping_ok": ping_ok, "ssh_open": ssh_open}

    return await asyncio.gather(*[_probe(ip) for ip in hosts])


async def detect_db_engines(
    ip: str,
    sem: Optional[asyncio.Semaphore] = None,
) -> list[dict]:
    """Probe each known DB port on `ip` and return detection results."""
    if sem is None:
        sem = asyncio.Semaphore(10)
    results = []
    for port, engine in _ENGINE_BY_PORT.items():
        is_open = await _check_port(ip, port, sem)
        results.append({"port": port, "engine": engine, "open": is_open})
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_network_scanner.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/network_scanner.py backend/tests/test_network_scanner.py
git commit -m "feat: add network scanner service (ping sweep, port-22 scan, DB engine detection)"
```

---

### Task 6: Provisioner factory refactor + update call sites

**Files:**
- Modify: `backend/app/services/provisioner/factory.py`
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/api/v1/servers.py`
- Modify: `backend/tests/test_factory.py`

**Interfaces:**
- Consumes: `open_tunnel` from `app.services.ssh_tunnel`, `decrypt` from `app.services.encryption`
- Produces: `get_provisioner(server, session=None) -> AsyncContextManager[DatabaseProvisioner]`

- [ ] **Step 1: Write a failing test for the new factory signature**

Open `backend/tests/test_factory.py` and add at the end:

```python
@pytest.mark.asyncio
async def test_get_provisioner_direct_no_machine_id():
    """Factory yields a provisioner immediately when no machine_id is set."""
    from app.services.provisioner.factory import get_provisioner
    from unittest.mock import MagicMock

    server = MagicMock()
    server.machine_id = None
    server.engine = "postgresql"
    server.admin_dsn = "postgresql://u:p@localhost:5432/db"
    server.id = 1
    server.warning_threshold_pct = 75.0
    server.critical_threshold_pct = 90.0

    async with get_provisioner(server) as provisioner:
        assert provisioner is not None
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend
python -m pytest tests/test_factory.py::test_get_provisioner_direct_no_machine_id -v
```

Expected: FAIL — `get_provisioner` is not an async context manager yet.

- [ ] **Step 3: Rewrite the factory**

Replace all content of `backend/app/services/provisioner/factory.py` with:

```python
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse, urlunparse

from app.services.provisioner.base import DatabaseProvisioner


def _rewrite_dsn(dsn: str, host: str, port: int) -> str:
    parsed = urlparse(dsn)
    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, _ = netloc.rsplit("@", 1)
        new_netloc = f"{userinfo}@{host}:{port}"
    else:
        new_netloc = f"{host}:{port}"
    return urlunparse(parsed._replace(netloc=new_netloc))


def _build_provisioner(server, dsn: str) -> DatabaseProvisioner:
    engine = server.engine
    api_key = getattr(server, "api_key", None)
    sid = server.id
    warn = server.warning_threshold_pct
    crit = server.critical_threshold_pct

    match engine:
        case "postgresql":
            from app.services.provisioner.postgresql import PostgreSQLProvisioner
            return PostgreSQLProvisioner(dsn=dsn, server_id=sid,
                                        warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "pgvector":
            from app.services.provisioner.pgvector import PgvectorProvisioner
            return PgvectorProvisioner(dsn=dsn, server_id=sid,
                                      warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mysql":
            from app.services.provisioner.mysql import MySQLProvisioner
            return MySQLProvisioner(dsn=dsn, server_id=sid,
                                   warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mongodb":
            from app.services.provisioner.mongodb import MongoDBProvisioner
            return MongoDBProvisioner(dsn=dsn, server_id=sid,
                                     warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "qdrant":
            from app.services.provisioner.qdrant import QdrantProvisioner
            return QdrantProvisioner(base_url=dsn, api_key=api_key, server_id=sid,
                                    warning_threshold_pct=warn, critical_threshold_pct=crit)
        case _:
            raise ValueError(f"Unknown engine: {engine!r}")


@asynccontextmanager
async def get_provisioner(server, session=None):
    admin_dsn = server.admin_dsn or ""

    if server.machine_id and session:
        from app.models.machine import Machine
        from app.models.ssh_key import SSHKey
        from app.services.encryption import decrypt
        from app.services.ssh_tunnel import open_tunnel

        machine = await session.get(Machine, server.machine_id)
        if not machine or machine.is_deleted:
            raise ValueError(f"Machine {server.machine_id} not found")
        ssh_key_rec = await session.get(SSHKey, machine.ssh_key_id)
        if not ssh_key_rec:
            raise ValueError(f"SSH key {machine.ssh_key_id} not found")

        key_material = decrypt(ssh_key_rec.encrypted_private_key)
        passphrase = decrypt(ssh_key_rec.passphrase_encrypted) if ssh_key_rec.passphrase_encrypted else None

        async with open_tunnel(
            host=machine.ip,
            ssh_port=machine.ssh_port,
            username=ssh_key_rec.username,
            key_material=key_material,
            db_port=server.port,
            passphrase=passphrase,
        ) as local_port:
            tunneled_dsn = _rewrite_dsn(admin_dsn, "127.0.0.1", local_port)
            yield _build_provisioner(server, tunneled_dsn)
    else:
        yield _build_provisioner(server, admin_dsn)
```

- [ ] **Step 4: Update tasks.py call site**

In `backend/app/workers/tasks.py`, change the provisioner usage block. Replace:

```python
        try:
            provisioner = get_provisioner(server)

            extensions: list[str] = db_template.extensions if db_template else []
```

with:

```python
        try:
            async with get_provisioner(server, session) as provisioner:
             extensions: list[str] = db_template.extensions if db_template else []
```

And move the closing of the try/except to match. The full try block becomes:

```python
        try:
            async with get_provisioner(server, session) as provisioner:
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
```

- [ ] **Step 5: Update _live_capacity in servers.py**

In `backend/app/api/v1/servers.py`, update `_live_capacity` to accept and pass a session:

```python
async def _live_capacity(server: Server, session: AsyncSession) -> CapacityMetrics:
    if not server.admin_dsn:
        return _UNKNOWN_CAPACITY(server.id)
    try:
        async with get_provisioner(server, session) as provisioner:
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

Update the two call sites that use `_live_capacity`. In `health_summary`:
```python
    capacities = await asyncio.gather(*[_live_capacity(s, session) for s in servers])
```

In `get_server_capacity`:
```python
    return await _live_capacity(server, session)
```

- [ ] **Step 6: Run all tests**

```bash
cd backend
python -m pytest tests/ -v
```

Expected: all tests PASS. Pay attention to `test_factory.py`, `test_provisioner.py`, `test_tasks_factory.py`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/provisioner/factory.py backend/app/workers/tasks.py backend/app/api/v1/servers.py backend/tests/test_factory.py
git commit -m "feat: refactor provisioner factory to async context manager with SSH tunnel support"
```

---

### Task 7: SSH keys API routes

**Files:**
- Create: `backend/app/api/v1/ssh_keys.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/api/test_ssh_keys.py`

**Interfaces:**
- Consumes: `SSHKeyCreate`, `SSHKeyRead`, `SSHKey` model, `encrypt` from `app.services.encryption`
- Produces: `GET/POST/DELETE /api/v1/ssh-keys`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_ssh_keys.py`:

```python
import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet


FERNET_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def patch_fernet(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", FERNET_KEY)
    with patch("app.services.encryption.settings") as m:
        m.FERNET_KEY = FERNET_KEY
        yield m


@pytest.mark.asyncio
async def test_create_and_list_ssh_key(client):
    # Generate a real throwaway RSA key for testing
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    r = await client.post("/api/v1/ssh-keys", json={
        "name": "my-key", "username": "ubuntu", "private_key": pem
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "my-key"
    assert "private_key" not in data
    assert "encrypted_private_key" not in data

    r2 = await client.get("/api/v1/ssh-keys")
    assert r2.status_code == 200
    assert any(k["name"] == "my-key" for k in r2.json())


@pytest.mark.asyncio
async def test_delete_ssh_key(client):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    r = await client.post("/api/v1/ssh-keys", json={
        "name": "delete-me", "username": "root", "private_key": pem
    })
    key_id = r.json()["id"]

    r2 = await client.delete(f"/api/v1/ssh-keys/{key_id}")
    assert r2.status_code == 200

    r3 = await client.get("/api/v1/ssh-keys")
    assert not any(k["id"] == key_id for k in r3.json())


@pytest.mark.asyncio
async def test_create_with_invalid_key_returns_422(client):
    r = await client.post("/api/v1/ssh-keys", json={
        "name": "bad", "username": "ubuntu", "private_key": "not-a-pem"
    })
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/api/test_ssh_keys.py -v
```

Expected: 404 or import errors — routes don't exist yet.

- [ ] **Step 3: Create the SSH keys router**

Create `backend/app/api/v1/ssh_keys.py`:

```python
import asyncssh
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.machine import Machine
from app.models.ssh_key import SSHKey
from app.schemas.ssh_key import SSHKeyCreate, SSHKeyRead
from app.services.encryption import encrypt

router = APIRouter(prefix="/ssh-keys", tags=["ssh-keys"])


def _validate_private_key(pem: str, passphrase: str | None = None) -> None:
    try:
        asyncssh.import_private_key(pem, passphrase=passphrase)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid private key: {exc}")


@router.post("", response_model=SSHKeyRead, status_code=201)
async def create_ssh_key(
    payload: SSHKeyCreate,
    session: AsyncSession = Depends(get_session),
):
    _validate_private_key(payload.private_key, payload.passphrase)
    record = SSHKey(
        name=payload.name,
        username=payload.username,
        encrypted_private_key=encrypt(payload.private_key),
        passphrase_encrypted=encrypt(payload.passphrase) if payload.passphrase else None,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return SSHKeyRead.model_validate(record)


@router.get("", response_model=list[SSHKeyRead])
async def list_ssh_keys(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(SSHKey))
    return [SSHKeyRead.model_validate(k) for k in result.scalars().all()]


@router.delete("/{key_id}", response_model=SSHKeyRead)
async def delete_ssh_key(key_id: int, session: AsyncSession = Depends(get_session)):
    record = await session.get(SSHKey, key_id)
    if not record:
        raise HTTPException(status_code=404, detail="SSH key not found")
    # Check no machine references this key
    result = await session.execute(
        select(Machine).where(Machine.ssh_key_id == key_id, Machine.is_deleted == False)  # noqa: E712
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="SSH key is in use by one or more machines")
    await session.delete(record)
    await session.commit()
    return SSHKeyRead.model_validate(record)
```

- [ ] **Step 4: Register the router**

Open `backend/app/api/v1/router.py` and add:

```python
from app.api.v1.ssh_keys import router as ssh_keys_router
```

And inside the `api_router` section:
```python
api_router.include_router(ssh_keys_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/api/test_ssh_keys.py -v
```

Expected: 3 PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/ssh_keys.py backend/app/api/v1/router.py backend/tests/api/test_ssh_keys.py
git commit -m "feat: add SSH keys CRUD API endpoints"
```

---

### Task 8: Machines API routes

**Files:**
- Create: `backend/app/api/v1/machines.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/api/test_machines.py`

**Interfaces:**
- Consumes: `MachineCreate`, `MachineUpdate`, `MachineRead`, `EngineDetectionResult`, `ScanRequest`, `ScanResult`
- Consumes: `open_ssh` from `app.services.ssh_tunnel`, `scan`, `detect_db_engines` from `app.services.network_scanner`
- Produces: `GET/POST/PUT/DELETE /api/v1/machines`, `POST /api/v1/machines/{id}/check`, `POST /api/v1/machines/{id}/detect-engines`, `POST /api/v1/machines/scan`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_machines.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

FERNET_KEY = Fernet.generate_key().decode()


def _make_pem():
    pk = rsa.generate_private_key(65537, 2048, default_backend())
    return pk.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture(autouse=True)
def patch_fernet(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", FERNET_KEY)
    with patch("app.services.encryption.settings") as m:
        m.FERNET_KEY = FERNET_KEY
        yield m


@pytest.fixture
async def ssh_key_id(client):
    r = await client.post("/api/v1/ssh-keys", json={
        "name": "test-key", "username": "ubuntu", "private_key": _make_pem()
    })
    return r.json()["id"]


@pytest.mark.asyncio
async def test_create_and_list_machine(client, ssh_key_id):
    r = await client.post("/api/v1/machines", json={
        "ip": "192.168.1.10", "ssh_port": 22, "ssh_key_id": ssh_key_id, "label": "dev-box"
    })
    assert r.status_code == 201
    data = r.json()
    assert data["ip"] == "192.168.1.10"
    assert data["status"] == "unknown"

    r2 = await client.get("/api/v1/machines")
    assert any(m["ip"] == "192.168.1.10" for m in r2.json())


@pytest.mark.asyncio
async def test_delete_machine(client, ssh_key_id):
    r = await client.post("/api/v1/machines", json={
        "ip": "192.168.1.20", "ssh_port": 22, "ssh_key_id": ssh_key_id
    })
    machine_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/machines/{machine_id}")
    assert r2.status_code == 200
    r3 = await client.get("/api/v1/machines")
    assert not any(m["id"] == machine_id for m in r3.json())


@pytest.mark.asyncio
async def test_check_machine_online(client, ssh_key_id):
    r = await client.post("/api/v1/machines", json={
        "ip": "192.168.1.30", "ssh_port": 22, "ssh_key_id": ssh_key_id
    })
    machine_id = r.json()["id"]

    mock_conn = MagicMock()
    mock_conn.get_server_host_key.return_value = None
    mock_conn.run = AsyncMock(side_effect=[
        MagicMock(stdout="myhost\n"),
        MagicMock(stdout="Linux myhost 5.15 #1 SMP\n"),
    ])

    with patch("app.services.ssh_tunnel.asyncssh.connect", new=AsyncMock(return_value=mock_conn)), \
         patch("app.services.ssh_tunnel.asyncssh.import_private_key", return_value=MagicMock()):
        r2 = await client.post(f"/api/v1/machines/{machine_id}/check")

    assert r2.status_code == 200
    assert r2.json()["status"] == "online"
    assert r2.json()["hostname"] == "myhost"


@pytest.mark.asyncio
async def test_scan_rejects_public_cidr(client):
    r = await client.post("/api/v1/machines/scan", json={"cidr": "8.8.8.0/24", "method": "port22"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_scan_private_cidr(client):
    with patch("app.api.v1.machines.scan", new=AsyncMock(return_value=[
        {"ip": "192.168.1.1", "ping_ok": False, "ssh_open": True},
    ])):
        r = await client.post("/api/v1/machines/scan", json={"cidr": "192.168.1.0/30", "method": "port22"})
    assert r.status_code == 200
    assert r.json()[0]["ip"] == "192.168.1.1"
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/api/test_machines.py -v
```

Expected: 404 or import errors — routes don't exist yet.

- [ ] **Step 3: Create the machines router**

Create `backend/app/api/v1/machines.py`:

```python
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.machine import Machine
from app.models.server import Server
from app.models.ssh_key import SSHKey
from app.schemas.machine import (
    EngineDetectionResult,
    MachineCreate,
    MachineRead,
    MachineUpdate,
    ScanRequest,
    ScanResult,
)
from app.services.encryption import decrypt
from app.services.network_scanner import NetworkScanError, detect_db_engines, scan
from app.services.ssh_tunnel import open_ssh

router = APIRouter(prefix="/machines", tags=["machines"])


async def _get_key_material(session: AsyncSession, machine: Machine) -> tuple[str, Optional[str]]:
    ssh_key_rec = await session.get(SSHKey, machine.ssh_key_id)
    if not ssh_key_rec:
        raise HTTPException(status_code=400, detail="SSH key not found for this machine")
    key_material = decrypt(ssh_key_rec.encrypted_private_key)
    passphrase = decrypt(ssh_key_rec.passphrase_encrypted) if ssh_key_rec.passphrase_encrypted else None
    return key_material, passphrase, ssh_key_rec.username


@router.post("", response_model=MachineRead, status_code=201)
async def create_machine(
    payload: MachineCreate,
    session: AsyncSession = Depends(get_session),
):
    machine = Machine(**payload.model_dump())
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.get("", response_model=list[MachineRead])
async def list_machines(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Machine).where(Machine.is_deleted == False)  # noqa: E712
    )
    return [MachineRead.model_validate(m) for m in result.scalars().all()]


@router.get("/{machine_id}", response_model=MachineRead)
async def get_machine(machine_id: int, session: AsyncSession = Depends(get_session)):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    return MachineRead.model_validate(machine)


@router.put("/{machine_id}", response_model=MachineRead)
async def update_machine(
    machine_id: int,
    payload: MachineUpdate,
    session: AsyncSession = Depends(get_session),
):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(machine, key, value)
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.delete("/{machine_id}", response_model=MachineRead)
async def delete_machine(machine_id: int, session: AsyncSession = Depends(get_session)):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    result = await session.execute(
        select(Server).where(Server.machine_id == machine_id, Server.is_deleted == False)  # noqa: E712
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Machine is in use by one or more servers")
    machine.is_deleted = True
    machine.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.post("/{machine_id}/check", response_model=MachineRead)
async def check_machine(machine_id: int, session: AsyncSession = Depends(get_session)):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")

    key_material, passphrase, username = await _get_key_material(session, machine)

    try:
        async with open_ssh(
            host=machine.ip,
            port=machine.ssh_port,
            username=username,
            key_material=key_material,
            passphrase=passphrase,
        ) as ssh:
            hostname = (await ssh.run("hostname")).strip()
            os_info = (await ssh.run("uname -a")).strip()
            fingerprint = ssh.host_fingerprint()

        machine.status = "online"
        machine.hostname = hostname or None
        machine.os_info = os_info or None
        machine.host_fingerprint = fingerprint
    except Exception as exc:
        machine.status = "offline"
        machine.os_info = str(exc)[:500]

    machine.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.post("/{machine_id}/detect-engines", response_model=list[EngineDetectionResult])
async def detect_engines(machine_id: int, session: AsyncSession = Depends(get_session)):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")

    results = await detect_db_engines(machine.ip)
    return [EngineDetectionResult(**r) for r in results]


@router.post("/scan", response_model=list[ScanResult])
async def scan_network(payload: ScanRequest):
    try:
        results = await scan(payload.cidr, payload.method)
    except NetworkScanError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return [ScanResult(**r) for r in results]
```

- [ ] **Step 4: Register the machines router**

Open `backend/app/api/v1/router.py` and add:

```python
from app.api.v1.machines import router as machines_router
```

And:
```python
api_router.include_router(machines_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/api/test_machines.py -v
```

Expected: 5 PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/machines.py backend/app/api/v1/router.py backend/tests/api/test_machines.py
git commit -m "feat: add machines CRUD + check + detect-engines + network scan API endpoints"
```

---

### Task 9: SQL console SSH guard

**Files:**
- Modify: `backend/app/api/v1/databases.py`
- Create: `backend/tests/test_databases_ssh_guard.py`

**Interfaces:**
- Consumes: `Server.machine_id`
- Produces: 400 response when `server.machine_id` is set and console is attempted

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_databases_ssh_guard.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_console_blocked_for_ssh_tunneled_server(client, db_session):
    from app.models.server import Server
    from app.models.creation_log import CreationLog
    from app.models.job import Job
    from datetime import datetime, timezone

    # Create a job and server with machine_id set
    server = Server(
        name="tunneled", host="192.168.1.10", port=5432,
        engine="postgresql", environment="development",
        machine_id=999,  # non-null machine_id triggers the guard
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)

    job = Job(
        db_name="testdb", environment="development",
        status="succeeded", owner="testuser", server_id=server.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    log = CreationLog(
        job_id=job.id, server_id=server.id,
        db_name="testdb",
        provisioned_at=datetime.now(timezone.utc),
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    with patch("app.api.v1.databases.get_current_user", return_value=MagicMock(is_admin=True)):
        r = await client.post(
            f"/api/v1/databases/{log.id}/query",
            json={"sql": "SELECT 1"},
        )
    assert r.status_code == 400
    assert "SSH-tunneled" in r.json()["detail"]
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend
python -m pytest tests/test_databases_ssh_guard.py -v
```

Expected: FAIL — the endpoint does not return 400 yet (it will return 400 "Server has no admin DSN" instead).

- [ ] **Step 3: Add the SSH guard to databases.py**

In `backend/app/api/v1/databases.py`, locate the `query_database` route handler. After the `server` check (`if not server or not server.admin_dsn`), add the SSH guard:

```python
    server = await session.get(Server, log.server_id)
    if not server or not server.admin_dsn:
        raise HTTPException(status_code=400, detail="Server has no admin DSN — set it in Servers before querying")

    if server.machine_id:
        raise HTTPException(
            status_code=400,
            detail="SQL console is not supported for SSH-tunneled servers in this version",
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
python -m pytest tests/test_databases_ssh_guard.py -v
```

Expected: PASSED.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
cd backend
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/databases.py backend/tests/test_databases_ssh_guard.py
git commit -m "feat: block SQL console for SSH-tunneled servers, return 400 with clear message"
```

---

### Task 10: Frontend types and API client

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

**Interfaces:**
- Produces: `SSHKey`, `SSHKeyCreate`, `Machine`, `MachineCreate`, `ScanResult`, `EngineDetectionResult` types
- Produces: `api.sshKeys.*`, `api.machines.*` methods

- [ ] **Step 1: Add new types to types.ts**

Open `frontend/src/types.ts` and append at the end:

```typescript
export interface SSHKey {
  id: number
  name: string
  username: string
  created_at: string
}

export interface SSHKeyCreate {
  name: string
  username: string
  private_key: string
  passphrase?: string
}

export interface Machine {
  id: number
  ip: string
  hostname: string | null
  label: string | null
  ssh_port: number
  ssh_key_id: number
  os_info: string | null
  host_fingerprint: string | null
  status: string
  last_checked_at: string | null
  created_at: string
  is_deleted: boolean
}

export interface MachineCreate {
  ip: string
  ssh_port?: number
  ssh_key_id: number
  label?: string
}

export interface ScanResult {
  ip: string
  ping_ok: boolean
  ssh_open: boolean
}

export interface EngineDetectionResult {
  port: number
  engine: string
  open: boolean
}
```

Also update the `ServerCreate` interface to add `machine_id`:

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
  machine_id?: number | null
}
```

And `Server` to expose `machine_id`:
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
  machine_id: number | null
  created_at: string
  is_deleted: boolean
}
```

- [ ] **Step 2: Add API client methods to api.ts**

Open `frontend/src/api.ts` and add to the import list at the top:

```typescript
import type {
  ApprovalPolicy, CreationLog, DBTemplate, DBTemplateCreate,
  EngineDetectionResult, HealthCheck, Job, JobCreate, Machine, MachineCreate,
  NamingProfile, NamingProfileCreate,
  Paginated, QueryResult, RequestTemplate, RequestTemplateCreate,
  ScanResult, Server, ServerCreate, SSHKey, SSHKeyCreate, Stats,
} from './types'
```

Then add before the closing `}` of the `api` object:

```typescript
  sshKeys: {
    list: () => req<SSHKey[]>('/ssh-keys'),
    create: (data: SSHKeyCreate) =>
      req<SSHKey>('/ssh-keys', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) =>
      req<SSHKey>(`/ssh-keys/${id}`, { method: 'DELETE' }),
  },
  machines: {
    list: () => req<Machine[]>('/machines'),
    create: (data: MachineCreate) =>
      req<Machine>('/machines', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<MachineCreate>) =>
      req<Machine>(`/machines/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) =>
      req<Machine>(`/machines/${id}`, { method: 'DELETE' }),
    check: (id: number) =>
      req<Machine>(`/machines/${id}/check`, { method: 'POST' }),
    detectEngines: (id: number) =>
      req<EngineDetectionResult[]>(`/machines/${id}/detect-engines`, { method: 'POST' }),
    scan: (data: { cidr: string; method: string }) =>
      req<ScanResult[]>('/machines/scan', { method: 'POST', body: JSON.stringify(data) }),
  },
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npm run build 2>&1 | head -30
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat: add SSHKey, Machine types and api client methods"
```

---

### Task 11: Frontend Systems page

**Files:**
- Create: `frontend/src/pages/Systems.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api.sshKeys.*`, `api.machines.*`, `SSHKey`, `Machine`, `ScanResult`, `EngineDetectionResult` from types
- Produces: Systems page with SSH Keys tab and Machines tab, reachable from nav

- [ ] **Step 1: Create the Systems page**

Create `frontend/src/pages/Systems.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { EngineDetectionResult, Machine, MachineCreate, ScanResult, SSHKey, SSHKeyCreate } from '../types'

type Tab = 'sshkeys' | 'machines'

// ── SSH Keys ──────────────────────────────────────────────────────────────────

function SSHKeys() {
  const [items, setItems] = useState<SSHKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<SSHKeyCreate>({ name: '', username: '', private_key: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    api.sshKeys.list().then(setItems).catch(e => setError(e.message)).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const set = (k: keyof SSHKeyCreate, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    try {
      await api.sshKeys.create({ ...form, passphrase: form.passphrase || undefined })
      setSuccess('SSH key saved.')
      setShowForm(false)
      setForm({ name: '', username: '', private_key: '' })
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSubmitting(false) }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete SSH key "${name}"?`)) return
    try { await api.sshKeys.delete(id); load() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  return (
    <div>
      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>SSH Keys</div>
        <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(s => !s); setError(''); setSuccess('') }}>
          {showForm ? 'Cancel' : '+ Add Key'}
        </button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}
      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="prod-deploy-key" />
              </div>
              <div className="form-group">
                <label>SSH Username *</label>
                <input required value={form.username} onChange={e => set('username', e.target.value)} placeholder="ubuntu" />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>Private Key (PEM) * <span style={{ color: 'var(--muted)', fontSize: 11 }}>write-only — not shown after save</span></label>
                <textarea
                  required rows={6}
                  value={form.private_key}
                  onChange={e => set('private_key', e.target.value)}
                  placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;..."
                  style={{ fontFamily: 'monospace', fontSize: 12, width: '100%', resize: 'vertical' }}
                />
              </div>
              <div className="form-group">
                <label>Passphrase <span style={{ color: 'var(--muted)', fontSize: 11 }}>(optional)</span></label>
                <input type="password" value={form.passphrase ?? ''} onChange={e => set('passphrase', e.target.value)} />
              </div>
            </div>
            <div className="row gap-2 mt-4" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Saving…' : 'Save Key'}
              </button>
            </div>
          </form>
        </div>
      )}
      {loading ? <div className="loading">Loading…</div> : items.length === 0 ? (
        <div className="empty">No SSH keys configured.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Username</th><th>Added</th><th></th></tr></thead>
            <tbody>
              {items.map(k => (
                <tr key={k.id}>
                  <td style={{ fontWeight: 500 }}>{k.name}</td>
                  <td><code>{k.username}</code></td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(k.created_at).toLocaleDateString()}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => remove(k.id, k.name)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Machines ──────────────────────────────────────────────────────────────────

function Machines() {
  const [machines, setMachines] = useState<Machine[]>([])
  const [sshKeys, setSshKeys] = useState<SSHKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [showScan, setShowScan] = useState(false)
  const [form, setForm] = useState<MachineCreate>({ ip: '', ssh_port: 22, ssh_key_id: 0 })
  const [scanForm, setScanForm] = useState({ cidr: '', method: 'port22' })
  const [scanResults, setScanResults] = useState<ScanResult[] | null>(null)
  const [scanning, setScanning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [checking, setChecking] = useState<number | null>(null)
  const [detecting, setDetecting] = useState<number | null>(null)
  const [detectResults, setDetectResults] = useState<{ machineId: number; results: EngineDetectionResult[] } | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    Promise.all([api.machines.list(), api.sshKeys.list()])
      .then(([m, k]) => { setMachines(m.filter(x => !x.is_deleted)); setSshKeys(k) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const setF = (k: keyof MachineCreate, v: string | number) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    try {
      await api.machines.create({ ...form, label: form.label || undefined })
      setSuccess('Machine registered.')
      setShowForm(false)
      setForm({ ip: '', ssh_port: 22, ssh_key_id: 0 })
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSubmitting(false) }
  }

  const check = async (id: number) => {
    setChecking(id); setError(''); setSuccess('')
    try {
      await api.machines.check(id)
      setSuccess('Connectivity check complete.')
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setChecking(null) }
  }

  const detectEngines = async (id: number) => {
    setDetecting(id); setError('')
    try {
      const results = await api.machines.detectEngines(id)
      setDetectResults({ machineId: id, results })
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setDetecting(null) }
  }

  const remove = async (id: number) => {
    if (!confirm('Delete this machine?')) return
    try { await api.machines.delete(id); load() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  const runScan = async (e: React.FormEvent) => {
    e.preventDefault()
    setScanning(true); setScanResults(null); setError('')
    try {
      const results = await api.machines.scan(scanForm)
      setScanResults(results)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setScanning(false) }
  }

  const STATUS_COLOR: Record<string, string> = {
    online: 'var(--green)', offline: 'var(--red)', unknown: 'var(--muted)'
  }

  return (
    <div>
      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>Machines</div>
        <div className="row gap-2">
          <button className="btn btn-sm" onClick={() => { setShowScan(s => !s); setError('') }}>
            {showScan ? 'Close Scan' : 'Scan Network'}
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(s => !s); setError('') }}>
            {showForm ? 'Cancel' : '+ Add Machine'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showScan && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="section-title" style={{ marginBottom: 12, fontSize: 14 }}>Network Scan</div>
          <form onSubmit={runScan}>
            <div className="grid-2">
              <div className="form-group">
                <label>CIDR Range *</label>
                <input required value={scanForm.cidr} onChange={e => setScanForm(f => ({ ...f, cidr: e.target.value }))}
                  placeholder="192.168.1.0/24" />
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>Private IP ranges only (RFC-1918)</div>
              </div>
              <div className="form-group">
                <label>Scan Method</label>
                <select value={scanForm.method} onChange={e => setScanForm(f => ({ ...f, method: e.target.value }))}>
                  <option value="port22">Port 22 only</option>
                  <option value="ping">Ping sweep only</option>
                  <option value="both">Ping + Port 22</option>
                </select>
              </div>
            </div>
            <button className="btn btn-primary btn-sm" type="submit" disabled={scanning}>
              {scanning ? 'Scanning…' : 'Start Scan'}
            </button>
          </form>
          {scanResults && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                {scanResults.filter(r => r.ssh_open || r.ping_ok).length} hosts found
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>IP</th><th>Ping</th><th>SSH (22)</th><th></th></tr></thead>
                  <tbody>
                    {scanResults.map(r => (
                      <tr key={r.ip}>
                        <td><code>{r.ip}</code></td>
                        <td style={{ color: r.ping_ok ? 'var(--green)' : 'var(--muted)' }}>{r.ping_ok ? '✓' : '—'}</td>
                        <td style={{ color: r.ssh_open ? 'var(--green)' : 'var(--muted)' }}>{r.ssh_open ? '✓' : '—'}</td>
                        <td>
                          {(r.ping_ok || r.ssh_open) && sshKeys.length > 0 && (
                            <button className="btn btn-sm" onClick={() => {
                              setForm(f => ({ ...f, ip: r.ip }))
                              setShowForm(true)
                            }}>Add</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>IP Address *</label>
                <input required value={form.ip} onChange={e => setF('ip', e.target.value)} placeholder="192.168.1.10" />
              </div>
              <div className="form-group">
                <label>SSH Port</label>
                <input type="number" value={form.ssh_port} onChange={e => setF('ssh_port', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>SSH Key *</label>
                <select required value={form.ssh_key_id} onChange={e => setF('ssh_key_id', Number(e.target.value))}>
                  <option value={0}>— select key —</option>
                  {sshKeys.map(k => <option key={k.id} value={k.id}>{k.name} ({k.username})</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Label</label>
                <input value={form.label ?? ''} onChange={e => setF('label', e.target.value)} placeholder="dev-box" />
              </div>
            </div>
            <div className="row gap-2 mt-4" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting || form.ssh_key_id === 0}>
                {submitting ? 'Adding…' : 'Add Machine'}
              </button>
            </div>
          </form>
        </div>
      )}

      {detectResults && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="row between" style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>
              Detected engines on {machines.find(m => m.id === detectResults.machineId)?.ip}
            </div>
            <button className="btn btn-sm" onClick={() => setDetectResults(null)}>Close</button>
          </div>
          <table>
            <thead><tr><th>Port</th><th>Engine</th><th>Status</th></tr></thead>
            <tbody>
              {detectResults.results.map(r => (
                <tr key={r.port}>
                  <td><code>{r.port}</code></td>
                  <td>{r.engine}</td>
                  <td style={{ color: r.open ? 'var(--green)' : 'var(--muted)' }}>
                    {r.open ? 'Listening' : 'Not found'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {loading ? <div className="loading">Loading…</div> : machines.length === 0 ? (
        <div className="empty">No machines registered. Add one manually or use Scan Network.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>IP / Label</th><th>Hostname</th><th>Status</th>
                <th>SSH Key</th><th>Last Checked</th><th></th>
              </tr>
            </thead>
            <tbody>
              {machines.map(m => (
                <tr key={m.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{m.label ?? m.ip}</div>
                    {m.label && <div style={{ fontSize: 11, color: 'var(--muted)' }}>{m.ip}</div>}
                  </td>
                  <td style={{ color: 'var(--muted)' }}>{m.hostname ?? '—'}</td>
                  <td>
                    <span style={{ color: STATUS_COLOR[m.status] ?? 'var(--muted)', fontSize: 13 }}>
                      ● {m.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {sshKeys.find(k => k.id === m.ssh_key_id)?.name ?? `#${m.ssh_key_id}`}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--muted)' }}>
                    {m.last_checked_at ? new Date(m.last_checked_at).toLocaleString() : '—'}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button
                      className="btn btn-sm"
                      style={{ marginRight: 4 }}
                      disabled={checking === m.id}
                      onClick={() => check(m.id)}
                    >
                      {checking === m.id ? 'Checking…' : 'Check'}
                    </button>
                    <button
                      className="btn btn-sm"
                      style={{ marginRight: 4 }}
                      disabled={detecting === m.id}
                      onClick={() => detectEngines(m.id)}
                    >
                      {detecting === m.id ? 'Detecting…' : 'Detect Engines'}
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => remove(m.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Systems root ──────────────────────────────────────────────────────────────

export default function Systems() {
  const [tab, setTab] = useState<Tab>('sshkeys')

  const TABS: { id: Tab; label: string }[] = [
    { id: 'sshkeys', label: 'SSH Keys' },
    { id: 'machines', label: 'Machines' },
  ]

  return (
    <>
      <h2 className="page-title">Systems</h2>
      <div className="row gap-2" style={{ marginBottom: 24, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '8px 16px', fontSize: 13, fontWeight: tab === t.id ? 600 : 400,
            color: tab === t.id ? 'var(--accent)' : 'var(--muted)',
            borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1,
          }}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'sshkeys' && <SSHKeys />}
      {tab === 'machines' && <Machines />}
    </>
  )
}
```

- [ ] **Step 2: Add Systems to App.tsx nav and routing**

Open `frontend/src/App.tsx`. Add the import:

```typescript
import Systems from './pages/Systems'
```

Update the `Page` type:
```typescript
type Page = 'dashboard' | 'servers' | 'jobs' | 'settings' | 'systems'
```

Update the `NAV` array (add before settings):
```typescript
  { id: 'systems', label: 'Systems', icon: '⬕' },
```

Add the route in the `<main>` block:
```tsx
        {page === 'systems' && <Systems />}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npm run build 2>&1 | head -30
```

Expected: no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Systems.tsx frontend/src/App.tsx
git commit -m "feat: add Systems page with SSH Keys and Machines tabs"
```

---

### Task 12: Server form SSH tunnel dropdown

**Files:**
- Modify: `frontend/src/pages/Servers.tsx`

**Interfaces:**
- Consumes: `api.machines.list()`, `Machine` type
- Produces: optional "SSH Tunnel via Machine" dropdown in the server create/edit form

- [ ] **Step 1: Update Servers.tsx**

Open `frontend/src/pages/Servers.tsx`. 

Add `Machine` to the import:
```typescript
import type { Machine, Server, ServerCreate } from '../types'
```

Add machine state inside the `Servers` component, after the existing `useState` declarations:
```typescript
  const [machines, setMachines] = useState<Machine[]>([])
```

Update the `load` function to also fetch machines:
```typescript
  const load = () => {
    setLoading(true)
    Promise.all([
      api.servers.list(),
      api.machines.list(),
    ])
      .then(([data, mList]) => {
        setServers(data.filter(s => !s.is_deleted))
        setMachines(mList.filter(m => !m.is_deleted))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
```

Update the `blank` form to include `machine_id`:
```typescript
const blank: ServerCreate = {
  name: '', host: '', port: 5432, engine: 'postgresql',
  environment: 'development', region: '', max_connections: 100, max_storage_gb: 100,
  warning_threshold_pct: 75, critical_threshold_pct: 90, machine_id: null,
}
```

Update `openEdit` to restore `machine_id`:
```typescript
  const openEdit = (s: Server) => {
    setEditingId(s.id)
    setForm({
      name: s.name, host: s.host, port: s.port, engine: s.engine,
      environment: s.environment, region: s.region ?? '',
      max_connections: s.max_connections, max_storage_gb: s.max_storage_gb,
      warning_threshold_pct: s.warning_threshold_pct,
      critical_threshold_pct: s.critical_threshold_pct,
      machine_id: s.machine_id ?? null,
    })
    setShowForm(true)
    setError('')
    setSuccess('')
  }
```

Inside the form's `<div className="grid-2">`, add the machine dropdown after the API Key field:
```tsx
              <div className="form-group">
                <label>
                  SSH Tunnel via Machine
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}> (optional — host/port are as seen from the machine)</span>
                </label>
                <select
                  value={form.machine_id ?? ''}
                  onChange={e => setForm(f => ({ ...f, machine_id: e.target.value ? Number(e.target.value) : null }))}
                >
                  <option value="">— direct connection —</option>
                  {machines.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.label ?? m.ip} ({m.ip})
                    </option>
                  ))}
                </select>
              </div>
```

Update the submit payload to include `machine_id` (it already spreads `form`, so no change needed to the `payload` construction — just verify `machine_id` is included in the spread).

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend
npm run build 2>&1 | head -30
```

Expected: no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Servers.tsx
git commit -m "feat: add SSH tunnel machine dropdown to Server create/edit form"
```

---

## Self-Review Checklist (run before declaring done)

- [ ] `python -m pytest tests/ -v` from `backend/` — all PASS
- [ ] `npm run build` from `frontend/` — no TypeScript errors
- [ ] `alembic upgrade head` runs cleanly on a fresh DB
- [ ] FERNET_KEY is set in `.env` before testing encryption-dependent endpoints
- [ ] Spec section 7 (Security): CIDR validation tested in `test_network_scanner.py` ✓
- [ ] Spec section 6 (Error handling): SSH key delete with machine reference returns 409 ✓
- [ ] Spec section 6: Machine delete with server reference returns 409 ✓
- [ ] Spec section 6: SQL console on SSH-tunneled server returns 400 ✓
- [ ] `machine_id` in `ServerRead` does NOT leak `admin_dsn` or `encrypted_private_key`

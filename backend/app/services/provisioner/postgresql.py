import re

import asyncpg

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

_ALLOWED_PRIVILEGES = frozenset(
    {"CONNECT", "TEMPORARY", "TEMP", "CREATE", "ALL"}
)

_ALLOWED_EXTENSIONS = frozenset(
    {
        "uuid-ossp", "pgcrypto", "hstore", "pg_trgm", "btree_gin", "btree_gist",
        "postgis", "citext", "ltree", "tablefunc", "unaccent", "pg_stat_statements",
        "vector", "intarray", "lo",
    }
)


def _quote_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


class PostgreSQLProvisioner(DatabaseProvisioner):
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

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self._dsn)

    async def database_exists(self, db_name: str) -> bool:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            return row is not None
        finally:
            await conn.close()

    async def create_database(self, spec: DatabaseSpec) -> DatabaseResult:
        if await self.database_exists(spec.name):
            return DatabaseResult(
                db_name=spec.name,
                success=False,
                message=f"Database '{spec.name}' already exists",
            )
        conn = await self._connect()
        try:
            db = _quote_identifier(spec.name)
            owner = _quote_identifier(spec.owner)
            await conn.execute(f"CREATE DATABASE {db} OWNER {owner}")
            return DatabaseResult(db_name=spec.name, success=True)
        except Exception as exc:
            return DatabaseResult(db_name=spec.name, success=False, message=str(exc))
        finally:
            await conn.close()

    async def create_user(self, spec: UserSpec) -> UserResult:
        conn = await self._connect()
        try:
            user = _quote_identifier(spec.username)
            # Use PostgreSQL's own quote_literal to safely escape the password
            quoted_password = await conn.fetchval("SELECT quote_literal($1)", spec.password)
            role_exists = await conn.fetchval(
                "SELECT 1 FROM pg_roles WHERE rolname = $1", spec.username
            )
            if role_exists:
                await conn.execute(f"ALTER USER {user} WITH PASSWORD {quoted_password}")
            else:
                await conn.execute(f"CREATE USER {user} WITH PASSWORD {quoted_password}")
            return UserResult(username=spec.username, success=True)
        except Exception as exc:
            return UserResult(username=spec.username, success=False, message=str(exc))
        finally:
            await conn.close()

    async def grant_permissions(self, spec: PermissionSpec) -> None:
        for priv in spec.privileges:
            if priv.upper() not in _ALLOWED_PRIVILEGES:
                raise ValueError(f"Privilege not allowed: {priv!r}")
        conn = await self._connect()
        try:
            privs = ", ".join(p.upper() for p in spec.privileges)
            db = _quote_identifier(spec.db_name)
            user = _quote_identifier(spec.username)
            await conn.execute(f"GRANT {privs} ON DATABASE {db} TO {user}")
        finally:
            await conn.close()

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        for ext in extensions:
            if ext not in _ALLOWED_EXTENSIONS:
                raise ValueError(f"Extension not allowed: {ext!r}")
        _quote_identifier(db_name)  # validate db_name before using in DSN
        db_dsn = self._dsn.rsplit("/", 1)[0] + f"/{db_name}"
        conn = await asyncpg.connect(db_dsn)
        try:
            for ext in extensions:
                quoted_ext = ext.replace('"', '""')
                await conn.execute(f'CREATE EXTENSION IF NOT EXISTS "{quoted_ext}"')
        finally:
            await conn.close()

    async def get_capacity(self) -> CapacityMetrics:
        conn = await self._connect()
        try:
            db_count = await conn.fetchval(
                "SELECT count(*) FROM pg_database WHERE datistemplate = false"
            )
            active_connections = await conn.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
            )
            disk_row = await conn.fetchrow(
                "SELECT pg_database_size(current_database()) AS used_bytes"
            )
            used_gb = (disk_row["used_bytes"] or 0) / (1024**3)
            return CapacityMetrics(
                server_id=self._server_id,
                db_count=int(db_count or 0),
                active_connections=int(active_connections or 0),
                disk_used_gb=round(used_gb, 2),
                disk_free_gb=0.0,
                warning_threshold_pct=self._warning_threshold_pct,
                critical_threshold_pct=self._critical_threshold_pct,
            )
        finally:
            await conn.close()

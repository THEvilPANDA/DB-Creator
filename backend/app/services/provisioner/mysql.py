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
            async with conn.cursor() as cur:
                await cur.execute("SHOW DATABASES LIKE %s", (db_name,))
                row = await cur.fetchone()
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
            async with conn.cursor() as cur:
                await cur.execute(
                    f"CREATE DATABASE `{spec.name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
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
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM mysql.user WHERE user = %s AND host = '%%'", (spec.username,)
                )
                exists = await cur.fetchone()
                if exists:
                    await cur.execute(
                        f"ALTER USER '{spec.username}'@'%%' IDENTIFIED BY '{escaped_pw}'"
                    )
                else:
                    await cur.execute(
                        f"CREATE USER '{spec.username}'@'%%' IDENTIFIED BY '{escaped_pw}'"
                    )
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
            async with conn.cursor() as cur:
                await cur.execute(
                    f"GRANT {privs} ON `{spec.db_name}`.* TO '{spec.username}'@'%%'"
                )
                await cur.execute("FLUSH PRIVILEGES")
        finally:
            conn.close()

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        pass  # MySQL has no server-side extensions equivalent to PostgreSQL

    async def get_capacity(self) -> CapacityMetrics:
        conn = await self._connect()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SHOW DATABASES")
                rows = await cur.fetchall()
                db_count = len([
                    r for r in rows
                    if r[0] not in ("information_schema", "performance_schema", "mysql", "sys")
                ])
                await cur.execute("SHOW STATUS LIKE 'Threads_connected'")
                status_row = await cur.fetchone()
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

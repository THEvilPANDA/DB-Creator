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
            await conn.execute(f'CREATE DATABASE "{spec.name}" OWNER "{spec.owner}"')
            return DatabaseResult(db_name=spec.name, success=True)
        except Exception as exc:
            return DatabaseResult(db_name=spec.name, success=False, message=str(exc))
        finally:
            await conn.close()

    async def create_user(self, spec: UserSpec) -> UserResult:
        conn = await self._connect()
        try:
            await conn.execute(
                f"CREATE USER \"{spec.username}\" WITH PASSWORD '{spec.password}'"
            )
            return UserResult(username=spec.username, success=True)
        except Exception as exc:
            return UserResult(username=spec.username, success=False, message=str(exc))
        finally:
            await conn.close()

    async def grant_permissions(self, spec: PermissionSpec) -> None:
        conn = await self._connect()
        try:
            privs = ", ".join(spec.privileges)
            await conn.execute(
                f'GRANT {privs} ON DATABASE "{spec.db_name}" TO "{spec.username}"'
            )
        finally:
            await conn.close()

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        db_dsn = self._dsn.rsplit("/", 1)[0] + f"/{db_name}"
        conn = await asyncpg.connect(db_dsn)
        try:
            for ext in extensions:
                await conn.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
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

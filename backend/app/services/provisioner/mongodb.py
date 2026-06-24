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

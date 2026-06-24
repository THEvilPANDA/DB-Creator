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

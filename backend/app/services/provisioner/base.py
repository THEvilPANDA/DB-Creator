from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseSpec:
    name: str
    owner: str
    extensions: list[str] = field(default_factory=list)
    template: Optional[str] = None


@dataclass
class DatabaseResult:
    db_name: str
    success: bool
    message: str = ""


@dataclass
class UserSpec:
    username: str
    password: str
    db_name: str


@dataclass
class UserResult:
    username: str
    success: bool
    message: str = ""


@dataclass
class PermissionSpec:
    db_name: str
    username: str
    privileges: list[str] = field(default_factory=lambda: ["CONNECT", "USAGE"])


class CapacityMetrics:
    def __init__(
        self,
        server_id: int,
        db_count: int,
        active_connections: int,
        disk_used_gb: float,
        disk_free_gb: float,
        warning_threshold_pct: float,
        critical_threshold_pct: float,
    ):
        self.server_id = server_id
        self.db_count = db_count
        self.active_connections = active_connections
        self.disk_used_gb = disk_used_gb
        self.disk_free_gb = disk_free_gb
        self.warning_threshold_pct = warning_threshold_pct
        self.critical_threshold_pct = critical_threshold_pct

    @property
    def health(self) -> str:
        if self.disk_free_gb == 0:
            return "healthy"
        total = self.disk_used_gb + self.disk_free_gb
        if total == 0:
            return "healthy"
        used_pct = (self.disk_used_gb / total) * 100
        if used_pct >= self.critical_threshold_pct:
            return "critical"
        if used_pct >= self.warning_threshold_pct:
            return "warning"
        return "healthy"


class DatabaseProvisioner(ABC):
    @abstractmethod
    async def create_database(self, spec: DatabaseSpec) -> DatabaseResult: ...

    @abstractmethod
    async def create_user(self, spec: UserSpec) -> UserResult: ...

    @abstractmethod
    async def grant_permissions(self, spec: PermissionSpec) -> None: ...

    @abstractmethod
    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None: ...

    @abstractmethod
    async def get_capacity(self) -> CapacityMetrics: ...

    @abstractmethod
    async def database_exists(self, db_name: str) -> bool: ...

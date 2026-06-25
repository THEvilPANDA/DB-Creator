from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


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
        # ORM object — extract fields manually so admin_dsn and api_key stay out of response
        d: dict = {}
        for fname in cls.model_fields:
            if fname == "has_admin_dsn":
                d["has_admin_dsn"] = bool(getattr(v, "admin_dsn", None))
            elif fname == "has_api_key":
                d["has_api_key"] = bool(getattr(v, "api_key", None))
            else:
                d[fname] = getattr(v, fname, None)
        return d


class CapacityMetrics(BaseModel):
    server_id: int
    db_count: int
    active_connections: int
    disk_used_gb: float
    disk_free_gb: float
    health: str


class ServerHealthEntry(BaseModel):
    server_id: int
    name: str
    environment: str
    health: str
    db_count: int
    active_connections: int
    disk_used_gb: float


class HealthSummaryResponse(BaseModel):
    servers: list[ServerHealthEntry]
    healthy: int
    warning: int
    critical: int
    unknown: int

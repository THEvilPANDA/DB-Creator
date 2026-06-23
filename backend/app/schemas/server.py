from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    is_active: Optional[bool] = None
    max_connections: Optional[int] = None
    max_storage_gb: Optional[float] = None
    warning_threshold_pct: Optional[float] = None
    critical_threshold_pct: Optional[float] = None


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
    created_at: datetime
    is_deleted: bool


class CapacityMetrics(BaseModel):
    server_id: int
    db_count: int
    active_connections: int
    disk_used_gb: float
    disk_free_gb: float
    health: str

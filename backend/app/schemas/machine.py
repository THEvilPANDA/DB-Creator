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
    version: Optional[str] = None
    databases: list[str] = []


class ScanRequest(BaseModel):
    cidr: str
    method: str  # "ping" | "port22" | "both"


class ScanResult(BaseModel):
    ip: str
    ping_ok: bool
    ssh_open: bool
    hostname: Optional[str] = None
    open_ports: list[int] = []

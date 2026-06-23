from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    db_name: Optional[str] = None
    environment: str
    owner: str
    team: Optional[str] = None
    cost_center: Optional[str] = None
    server_id: Optional[int] = None
    naming_profile_id: Optional[int] = None
    db_template_id: Optional[int] = None
    request_template_id: Optional[int] = None
    expires_at: Optional[datetime] = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    db_name: str
    environment: str
    status: str
    owner: str
    team: Optional[str]
    cost_center: Optional[str]
    server_id: Optional[int]
    db_template_id: Optional[int]
    request_template_id: Optional[int]
    expires_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    is_deleted: bool

from typing import Optional

from pydantic import BaseModel, ConfigDict


class RequestTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    environment: str
    db_template_id: Optional[int] = None
    naming_profile_id: Optional[int] = None
    expiration_days: int = 90
    cost_center: Optional[str] = None
    team: Optional[str] = None


class RequestTemplateUpdate(BaseModel):
    name: Optional[str] = None
    environment: Optional[str] = None
    db_template_id: Optional[int] = None
    expiration_days: Optional[int] = None
    team: Optional[str] = None
    cost_center: Optional[str] = None


class RequestTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    environment: str
    db_template_id: Optional[int]
    naming_profile_id: Optional[int]
    expiration_days: int
    cost_center: Optional[str]
    team: Optional[str]
    is_deleted: bool

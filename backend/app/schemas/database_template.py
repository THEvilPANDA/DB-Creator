from typing import Optional

from pydantic import BaseModel, ConfigDict


class DatabaseTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    extensions: list[str] = []
    permissions: dict = {}


class DatabaseTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    extensions: Optional[list[str]] = None
    permissions: Optional[dict] = None


class DatabaseTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    extensions: list
    permissions: dict
    is_deleted: bool

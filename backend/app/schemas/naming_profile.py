from typing import Optional

from pydantic import BaseModel, ConfigDict


class NamingProfileCreate(BaseModel):
    name: str
    pattern: str
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    separator: str = "_"
    reserved_names: list[str] = []
    allow_collision: bool = False
    description: Optional[str] = None


class NamingProfileUpdate(BaseModel):
    name: Optional[str] = None
    pattern: Optional[str] = None
    reserved_names: Optional[list[str]] = None
    allow_collision: Optional[bool] = None
    description: Optional[str] = None


class NamingProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pattern: str
    prefix: Optional[str]
    suffix: Optional[str]
    separator: str
    reserved_names: list
    allow_collision: bool
    description: Optional[str]
    is_deleted: bool

from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NamingProfile(SQLModel, table=True):
    __tablename__ = "naming_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    pattern: str = Field(max_length=500)
    prefix: Optional[str] = Field(default=None, max_length=100)
    suffix: Optional[str] = Field(default=None, max_length=100)
    separator: str = Field(default="_", max_length=10)
    reserved_names: list = Field(
        default_factory=list,
        sa_column=sa.Column(sa.JSON, default=list),
    )
    allow_collision: bool = Field(default=False)
    description: Optional[str] = Field(default=None, max_length=1000)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow),
    )

    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)

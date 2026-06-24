from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DatabaseTemplate(SQLModel, table=True):
    __tablename__ = "database_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    extensions: list = Field(
        default_factory=list,
        sa_column=sa.Column(sa.JSON, default=list),
    )
    permissions: dict = Field(
        default_factory=dict,
        sa_column=sa.Column(sa.JSON, default=dict),
    )

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow),
    )

    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)


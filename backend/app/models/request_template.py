from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RequestTemplate(SQLModel, table=True):
    __tablename__ = "request_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    environment: str = Field(max_length=50)
    db_template_id: Optional[int] = Field(default=None, foreign_key="database_templates.id")
    naming_profile_id: Optional[int] = Field(default=None, foreign_key="naming_profiles.id")
    expiration_days: int = Field(default=90)
    cost_center: Optional[str] = Field(default=None, max_length=255)
    team: Optional[str] = Field(default=None, max_length=255)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow),
    )

    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)


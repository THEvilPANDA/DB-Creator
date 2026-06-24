from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    db_name: str = Field(max_length=255)
    environment: str = Field(max_length=50)
    status: str = Field(default="pending", max_length=50)

    server_id: Optional[int] = Field(default=None, foreign_key="servers.id")
    naming_profile_id: Optional[int] = Field(default=None, foreign_key="naming_profiles.id")
    db_template_id: Optional[int] = Field(default=None, foreign_key="database_templates.id")
    request_template_id: Optional[int] = Field(default=None, foreign_key="request_templates.id")

    owner: str = Field(max_length=255)
    team: Optional[str] = Field(default=None, max_length=255)
    cost_center: Optional[str] = Field(default=None, max_length=255)

    expires_at: Optional[datetime] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow),
    )

    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)


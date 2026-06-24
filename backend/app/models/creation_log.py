from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CreationLog(SQLModel, table=True):
    __tablename__ = "creation_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id")
    server_id: int = Field(foreign_key="servers.id")
    db_name: str = Field(max_length=255)
    db_user: Optional[str] = Field(default=None, max_length=255)
    connection_uri: Optional[str] = Field(default=None)
    iac_yaml: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text))
    iac_terraform: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text))
    provisioned_at: datetime = Field(default_factory=_utcnow)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)


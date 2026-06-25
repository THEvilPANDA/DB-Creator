from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Machine(SQLModel, table=True):
    __tablename__ = "machines"

    id: Optional[int] = Field(default=None, primary_key=True)
    ip: str = Field(max_length=45)
    hostname: Optional[str] = Field(default=None, max_length=255)
    label: Optional[str] = Field(default=None, max_length=255)
    ssh_port: int = Field(default=22)
    ssh_key_id: int = Field(foreign_key="ssh_keys.id")
    os_info: Optional[str] = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    host_fingerprint: Optional[str] = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    status: str = Field(default="unknown", max_length=20)
    last_checked_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)

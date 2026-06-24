from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Server(SQLModel, table=True):
    __tablename__ = "servers"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    host: str = Field(max_length=255)
    port: int = Field(default=5432)
    engine: str = Field(default="postgresql", max_length=50)
    environment: str = Field(max_length=50)
    region: Optional[str] = Field(default=None, max_length=100)
    is_active: bool = Field(default=True)

    max_connections: int = Field(default=100)
    max_storage_gb: float = Field(default=100.0)
    warning_threshold_pct: float = Field(default=75.0)
    critical_threshold_pct: float = Field(default=90.0)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow),
    )

    # Encrypted admin DSN used by the provisioner for capacity checks.
    # WARNING: store encrypted in production (see backlog: Fernet encryption).
    admin_dsn: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))

    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)


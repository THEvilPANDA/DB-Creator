from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    actor: str = Field(max_length=255)
    action: str = Field(max_length=100)
    entity_type: str = Field(max_length=100)
    entity_id: Optional[int] = Field(default=None)
    payload: Optional[dict] = Field(default=None, sa_column=sa.Column(sa.JSON))
    ip_address: Optional[str] = Field(default=None, max_length=45)
    created_at: datetime = Field(default_factory=_utcnow)


from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalRequest(SQLModel, table=True):
    __tablename__ = "approval_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id")
    approver: Optional[str] = Field(default=None, max_length=255)
    status: str = Field(default="pending", max_length=50)
    comments: Optional[str] = Field(default=None)
    decided_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(default=None)

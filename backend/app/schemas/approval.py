from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class ApprovalDecide(BaseModel):
    status: Literal["approved", "rejected"]
    comments: Optional[str] = None
    approver: str = "system"


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    approver: Optional[str]
    status: str
    comments: Optional[str]
    decided_at: Optional[datetime]
    created_at: datetime

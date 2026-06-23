from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    server_id: int
    db_name: str
    db_user: Optional[str]
    connection_uri: Optional[str]
    iac_yaml: Optional[str]
    iac_terraform: Optional[str]
    provisioned_at: datetime
    created_at: datetime
    is_deleted: bool

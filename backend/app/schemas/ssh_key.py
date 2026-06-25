from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SSHKeyCreate(BaseModel):
    name: str
    username: str
    private_key: str
    passphrase: Optional[str] = None


class SSHKeyRead(BaseModel):
    id: int
    name: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}

from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SSHKey(SQLModel, table=True):
    __tablename__ = "ssh_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    username: str = Field(max_length=255)
    encrypted_private_key: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    passphrase_encrypted: Optional[str] = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    created_at: datetime = Field(default_factory=_utcnow)

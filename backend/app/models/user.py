from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(
        sa_column=sa.Column(sa.String(100), unique=True, nullable=False, index=True)
    )
    email: str = Field(
        sa_column=sa.Column(sa.String(255), unique=True, nullable=False)
    )
    password_hash: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )


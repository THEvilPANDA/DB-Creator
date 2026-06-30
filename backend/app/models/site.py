from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Site(SQLModel, table=True):
    __tablename__ = "sites"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    template: str = Field(max_length=255)
    subdomain: str = Field(max_length=255)
    domain: str = Field(max_length=255)
    prefix: Optional[str] = Field(default=None, max_length=255)
    routing_mode: str = Field(default="port", max_length=20)
    app_port: Optional[int] = Field(default=None)
    web_root: str = Field(default="/var/www", max_length=255)
    directory: Optional[str] = Field(default=None, max_length=500)
    web_server: str = Field(default="apache", max_length=20)
    notes: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow),
    )
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None, max_length=255)


class SiteDeployment(SQLModel, table=True):
    __tablename__ = "site_deployments"

    id: Optional[int] = Field(default=None, primary_key=True)
    site_id: int = Field(foreign_key="sites.id")
    server_id: int = Field(foreign_key="servers.id")
    status: str = Field(default="active", max_length=20)
    port: Optional[int] = Field(default=None)
    directory: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=_utcnow)
    retired_at: Optional[datetime] = Field(default=None)


class SiteMigration(SQLModel, table=True):
    __tablename__ = "site_migrations"

    id: Optional[int] = Field(default=None, primary_key=True)
    site_id: int = Field(foreign_key="sites.id")
    source_deployment_id: Optional[int] = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("site_deployments.id"), nullable=True),
    )
    target_server_id: int = Field(foreign_key="servers.id")
    status: str = Field(default="pending", max_length=20)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    log: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    created_at: datetime = Field(default_factory=_utcnow)

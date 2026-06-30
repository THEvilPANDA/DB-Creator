from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

_VALID_ROUTING_MODES = {"port", "directory"}
_VALID_WEB_SERVERS = {"apache", "haproxy"}


class SiteCreate(BaseModel):
    name: str
    template: str
    subdomain: str
    domain: str
    prefix: Optional[str] = None
    routing_mode: str = "port"
    app_port: Optional[int] = None
    web_root: str = "/var/www"
    directory: Optional[str] = None
    web_server: str = "apache"
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "SiteCreate":
        if self.routing_mode not in _VALID_ROUTING_MODES:
            raise ValueError(f"routing_mode must be one of {_VALID_ROUTING_MODES}")
        if self.web_server not in _VALID_WEB_SERVERS:
            raise ValueError(f"web_server must be one of {_VALID_WEB_SERVERS}")
        if self.routing_mode == "port" and self.app_port is None:
            raise ValueError("app_port is required when routing_mode is 'port'")
        if self.routing_mode == "directory" and not self.directory:
            raise ValueError("directory is required when routing_mode is 'directory'")
        return self


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    template: Optional[str] = None
    subdomain: Optional[str] = None
    domain: Optional[str] = None
    prefix: Optional[str] = None
    routing_mode: Optional[str] = None
    app_port: Optional[int] = None
    web_root: Optional[str] = None
    directory: Optional[str] = None
    web_server: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "SiteUpdate":
        if self.routing_mode is not None and self.routing_mode not in _VALID_ROUTING_MODES:
            raise ValueError(f"routing_mode must be one of {_VALID_ROUTING_MODES}")
        if self.web_server is not None and self.web_server not in _VALID_WEB_SERVERS:
            raise ValueError(f"web_server must be one of {_VALID_WEB_SERVERS}")
        return self


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    template: str
    subdomain: str
    domain: str
    prefix: Optional[str] = None
    routing_mode: str
    app_port: Optional[int] = None
    web_root: str
    directory: Optional[str] = None
    web_server: str
    notes: Optional[str] = None
    created_at: datetime
    is_deleted: bool

    @property
    def web_url(self) -> str:
        return f"{self.subdomain}.{self.domain}"


class SiteDeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    server_id: int
    status: str
    port: Optional[int]
    directory: Optional[str]
    created_at: datetime
    retired_at: Optional[datetime]


class MigrationCreate(BaseModel):
    site_id: int
    target_server_id: int


class MigrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    source_deployment_id: Optional[int]
    target_server_id: int
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    log: Optional[str]
    created_at: datetime

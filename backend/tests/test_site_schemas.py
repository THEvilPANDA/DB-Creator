import pytest
from pydantic import ValidationError

from app.schemas.site import MigrationCreate, SiteCreate, SiteRead, SiteUpdate


def test_port_routing_requires_app_port():
    with pytest.raises(ValidationError, match="app_port"):
        SiteCreate(name="x", template="t", subdomain="s", domain="d.com", routing_mode="port")


def test_directory_routing_requires_directory():
    with pytest.raises(ValidationError, match="directory"):
        SiteCreate(name="x", template="t", subdomain="s", domain="d.com", routing_mode="directory")


def test_port_routing_valid():
    s = SiteCreate(
        name="mysite", template="tmpl", subdomain="app", domain="example.com",
        routing_mode="port", app_port=4007,
    )
    assert s.app_port == 4007
    assert s.web_server == "apache"


def test_directory_routing_valid():
    s = SiteCreate(
        name="x", template="t", subdomain="s", domain="d.com",
        routing_mode="directory", directory="/var/www/myapp",
    )
    assert s.directory == "/var/www/myapp"


def test_invalid_routing_mode():
    with pytest.raises(ValidationError, match="routing_mode"):
        SiteCreate(
            name="x", template="t", subdomain="s", domain="d.com",
            routing_mode="nginx_proxy", app_port=80,
        )


def test_invalid_web_server():
    with pytest.raises(ValidationError, match="web_server"):
        SiteCreate(
            name="x", template="t", subdomain="s", domain="d.com",
            routing_mode="port", app_port=80, web_server="nginx",
        )


def test_update_invalid_routing_mode():
    with pytest.raises(ValidationError, match="routing_mode"):
        SiteUpdate(routing_mode="bad")


def test_update_valid_partial():
    u = SiteUpdate(name="new-name")
    assert u.name == "new-name"
    assert u.routing_mode is None


def test_update_valid_web_server():
    u = SiteUpdate(web_server="haproxy")
    assert u.web_server == "haproxy"


def test_site_read_web_url():
    from datetime import datetime
    r = SiteRead(
        id=1, name="x", template="t", subdomain="app", domain="example.com",
        prefix=None, routing_mode="port", app_port=4007, web_root="/var/www",
        directory=None, web_server="apache", notes=None,
        created_at=datetime(2026, 1, 1), is_deleted=False,
    )
    assert r.web_url == "app.example.com"


def test_migration_create():
    m = MigrationCreate(site_id=1, target_server_id=5)
    assert m.target_server_id == 5

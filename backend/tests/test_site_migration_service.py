import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


async def test_find_free_port_returns_preferred_when_free():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="")
    from app.services.site_migration import find_free_port
    assert await find_free_port(ssh, 4007) == 4007
    ssh.run.assert_called_once()
    assert ":4007 " in ssh.run.call_args[0][0]


async def test_find_free_port_skips_occupied_port():
    ssh = MagicMock()
    calls = []
    async def _run(cmd):
        calls.append(cmd)
        return "LISTEN" if ":4007 " in cmd else ""
    ssh.run = _run
    from app.services.site_migration import find_free_port
    port = await find_free_port(ssh, 4007)
    assert port == 4008
    assert len(calls) == 2


async def test_ensure_web_root_runs_mkdir():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="ok")
    from app.services.site_migration import ensure_web_root
    result = await ensure_web_root(ssh, "/var/www")
    ssh.run.assert_called_once_with("mkdir -p /var/www && echo ok")
    assert result == "ok"


async def test_write_apache_vhost_port_mode():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="")
    site = MagicMock()
    site.subdomain = "app"
    site.domain = "example.com"
    site.prefix = None
    site.routing_mode = "port"
    from app.services.site_migration import write_apache_vhost
    await write_apache_vhost(ssh, site, 4007, "/var/www/app")
    cmd = ssh.run.call_args[0][0]
    assert "ProxyPass" in cmd
    assert "4007" in cmd
    assert "app.example.com" in cmd


async def test_write_apache_vhost_directory_mode():
    ssh = MagicMock()
    ssh.run = AsyncMock(return_value="")
    site = MagicMock()
    site.subdomain = "blog"
    site.domain = "example.com"
    site.prefix = None
    site.routing_mode = "directory"
    from app.services.site_migration import write_apache_vhost
    await write_apache_vhost(ssh, site, 0, "/var/www/blog")
    cmd = ssh.run.call_args[0][0]
    assert "DocumentRoot" in cmd
    assert "/var/www/blog" in cmd


async def test_write_haproxy_backend_returns_todo():
    ssh = MagicMock()
    site = MagicMock()
    site.subdomain = "app"
    site.domain = "example.com"
    from app.services.site_migration import write_haproxy_backend
    result = await write_haproxy_backend(ssh, site, 4007)
    assert "TODO" in result
    ssh.run.assert_not_called()


@pytest.mark.asyncio
async def test_write_apache_vhost_rejects_newline_in_prefix():
    from app.services.site_migration import write_apache_vhost

    site = SimpleNamespace(
        subdomain="app", domain="example.com",
        prefix="/x\nSetHandler server-status",
        routing_mode="port", directory=None,
        web_root="/var/www", web_server="apache",
    )
    with pytest.raises(ValueError, match="prefix contains invalid characters"):
        await write_apache_vhost(None, site, 3000, "/var/www/app")


@pytest.mark.asyncio
async def test_resolve_machine_ssh_fails_without_host_fingerprint():
    from app.services.site_migration import _resolve_machine_ssh

    machine = MagicMock()
    machine.id = 1
    machine.ip = "1.2.3.4"
    machine.is_deleted = False
    machine.host_fingerprint = None
    machine.ssh_key_id = 1

    ssh_key = MagicMock()
    ssh_key.encrypted_private_key = "key"
    ssh_key.passphrase_encrypted = None
    ssh_key.username = "ubuntu"

    session = MagicMock()
    session.get = AsyncMock(side_effect=[machine, ssh_key])

    server = MagicMock()
    server.machine_id = 1
    server.name = "test"
    server.id = 42

    with pytest.raises(ValueError, match="no verified host key"):
        await _resolve_machine_ssh(session, server)

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

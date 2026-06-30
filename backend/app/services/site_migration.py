import re
import shlex
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.machine import Machine
from app.models.server import Server
from app.models.site import Site, SiteDeployment, SiteMigration
from app.models.ssh_key import SSHKey
from app.services.encryption import decrypt
from app.services.ssh_tunnel import SSHConnection, open_ssh


_DNS_LABEL_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9-]*$')
_SAFE_PATH_RE = re.compile(r'^[a-zA-Z0-9/_.\-]+$')
_SAFE_PREFIX_RE = re.compile(r'^(/[a-zA-Z0-9/_.\-]*)?$')


def _validate_dns_label(value: str, field: str) -> None:
    for label in value.replace('_', '-').split('.'):
        if not label or not _DNS_LABEL_RE.match(label):
            raise ValueError(f"{field} contains invalid characters: {value!r}")


def _validate_path(value: str, field: str) -> None:
    if not value or not _SAFE_PATH_RE.match(value):
        raise ValueError(f"{field} contains invalid characters for a filesystem path: {value!r}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _resolve_machine_ssh(session: AsyncSession, server: Server):
    """Return (machine, key_material, passphrase, username) for server.machine_id."""
    if not server.machine_id:
        raise ValueError(f"Server '{server.name}' (id={server.id}) has no machine configured")
    machine = await session.get(Machine, server.machine_id)
    if not machine or machine.is_deleted:
        raise ValueError(f"Machine {server.machine_id} not found or deleted")
    if not machine.host_fingerprint:
        raise ValueError(
            f"Machine {machine.id} ({machine.ip}) has no verified host key. "
            "Run a connectivity check on this machine before provisioning."
        )
    ssh_key_rec = await session.get(SSHKey, machine.ssh_key_id)
    if not ssh_key_rec:
        raise ValueError(f"SSH key {machine.ssh_key_id} not found")
    key_material = decrypt(ssh_key_rec.encrypted_private_key)
    passphrase = decrypt(ssh_key_rec.passphrase_encrypted) if ssh_key_rec.passphrase_encrypted else None
    return machine, key_material, passphrase, ssh_key_rec.username


async def ensure_web_root(ssh: SSHConnection, web_root: str) -> str:
    return await ssh.run(f"mkdir -p {shlex.quote(web_root)} && echo ok")


async def find_free_port(ssh: SSHConnection, preferred_port: int) -> int:
    """Return preferred_port if free on the remote host, else the next free port."""
    result = await ssh.run(f"ss -tlnp 2>/dev/null | grep ':{preferred_port} ' | head -1")
    if not result.strip():
        return preferred_port
    for candidate in range(preferred_port + 1, preferred_port + 100):
        check = await ssh.run(f"ss -tlnp 2>/dev/null | grep ':{candidate} ' | head -1")
        if not check.strip():
            return candidate
    raise RuntimeError(f"No free port found in range {preferred_port}–{preferred_port + 99}")


async def write_apache_vhost(ssh: SSHConnection, site, port: int, site_dir: str) -> str:
    # Assumes Debian/Ubuntu apache2 layout: /etc/apache2/sites-available/
    # TODO: RHEL/CentOS uses /etc/httpd/conf.d/ — operator must verify distro layout.
    _validate_dns_label(site.subdomain, "subdomain")
    for label in site.domain.split('.'):
        _validate_dns_label(label, "domain")
    _validate_path(site_dir, "site_dir")
    web_url = f"{site.subdomain}.{site.domain}"
    vhost_name = f"{site.subdomain}-{site.domain.replace('.', '-')}"
    prefix = (site.prefix or "").rstrip("/")
    if prefix and not _SAFE_PREFIX_RE.match(prefix):
        raise ValueError(f"prefix contains invalid characters: {prefix!r}")

    if site.routing_mode == "port":
        body = (
            f"<VirtualHost *:80>\n"
            f"    ServerName {web_url}\n"
            f"    ProxyPreserveHost On\n"
            f"    ProxyPass {prefix}/ http://127.0.0.1:{port}/\n"
            f"    ProxyPassReverse {prefix}/ http://127.0.0.1:{port}/\n"
            f"</VirtualHost>"
        )
    else:
        body = (
            f"<VirtualHost *:80>\n"
            f"    ServerName {web_url}\n"
            f"    DocumentRoot {site_dir}\n"
            f"    <Directory {site_dir}>\n"
            f"        Options Indexes FollowSymLinks\n"
            f"        AllowOverride All\n"
            f"        Require all granted\n"
            f"    </Directory>\n"
            f"</VirtualHost>"
        )

    vhost_path = f"/etc/apache2/sites-available/{vhost_name}.conf"
    escaped = body.replace("\\", "\\\\").replace("'", "'\\''")
    cmd = (
        f"echo '{escaped}' | sudo tee {shlex.quote(vhost_path)} > /dev/null && "
        f"sudo a2ensite {shlex.quote(vhost_name)} && "
        f"sudo systemctl reload apache2 2>/dev/null || true"
    )
    return await ssh.run(cmd)


async def write_haproxy_backend(ssh: SSHConnection, site, port: int) -> str:
    # TODO: haproxy config modification is operator-specific — depends on whether haproxy.cfg
    # is managed via template, puppet/ansible, or hand-edited. This stub logs the intent
    # and returns a clear TODO message. Operator must add the backend manually or wire up
    # their config management tool. See MIGRATION_MODULE.md for details.
    backend_name = f"be_{site.subdomain}_{site.domain.replace('.', '_')}"
    web_url = f"{site.subdomain}.{site.domain}"
    return (
        f"TODO: add haproxy backend '{backend_name}' on port {port} for {web_url} — "
        f"configure manually in /etc/haproxy/haproxy.cfg"
    )


async def _best_effort_rsync(
    ssh: SSHConnection,
    source_ip: str,
    source_dir: str,
    target_dir: str,
) -> str:
    # TODO: rsync requires SSH key-based access from the source machine to the target machine,
    # or SSH agent forwarding. Neither is guaranteed. This is a best-effort step; failure
    # is logged but does not abort the migration. See MIGRATION_MODULE.md for alternatives.
    result = await ssh.run(
        f"rsync -avz --delete {shlex.quote(source_ip)}:{shlex.quote(source_dir)}/ {shlex.quote(target_dir)}/ 2>&1 | tail -10"
    )
    return result or "(no rsync output)"


async def run_migration(session: AsyncSession, migration: SiteMigration) -> None:
    """
    Execute a site migration in place. Mutates migration.status/log/error_message.
    Caller must NOT commit before calling; this function manages its own commits.
    """
    log_lines: list[str] = []

    def _log(msg: str) -> None:
        log_lines.append(msg)
        migration.log = "\n".join(log_lines)

    migration.status = "running"
    migration.started_at = _utcnow()
    session.add(migration)
    await session.commit()

    try:
        site = await session.get(Site, migration.site_id)
        if not site:
            raise ValueError(f"Site {migration.site_id} not found")
        _log(f"Site: {site.name} ({site.subdomain}.{site.domain})")

        target_server = await session.get(Server, migration.target_server_id)
        if not target_server or target_server.is_deleted:
            raise ValueError(f"Target server {migration.target_server_id} not found")
        _log(f"Target server: {target_server.name} (id={target_server.id})")

        machine, key_material, passphrase, username = await _resolve_machine_ssh(session, target_server)
        _log(f"Connecting via machine {machine.ip}:{machine.ssh_port} as {username}")

        target_dep = SiteDeployment(
            site_id=site.id,
            server_id=target_server.id,
            status="staging",
        )
        session.add(target_dep)
        await session.commit()
        await session.refresh(target_dep)
        _log(f"Created staging deployment id={target_dep.id}")

        _validate_path(site.web_root, "web_root")
        site_subdir = site.directory or site.subdomain
        site_dir = f"{site.web_root}/{site_subdir}"
        _validate_path(site_dir, "site_dir")

        async with open_ssh(
            host=machine.ip,
            port=machine.ssh_port,
            username=username,
            key_material=key_material,
            passphrase=passphrase,
            known_hosts_entry=machine.host_fingerprint,
        ) as ssh:
            _log("SSH connected")

            await ensure_web_root(ssh, site.web_root)
            _log(f"Ensured web_root: {site.web_root}")

            await ssh.run(f"mkdir -p {shlex.quote(site_dir)}")
            target_dep.directory = site_dir
            _log(f"Created site directory: {site_dir}")

            if site.routing_mode == "port":
                resolved_port = await find_free_port(ssh, site.app_port)
                target_dep.port = resolved_port
                _log(f"Resolved port: {resolved_port}")
                if site.web_server == "apache":
                    ws_out = await write_apache_vhost(ssh, site, resolved_port, site_dir)
                else:
                    ws_out = await write_haproxy_backend(ssh, site, resolved_port)
            else:
                resolved_port = None
                if site.web_server == "apache":
                    ws_out = await write_apache_vhost(ssh, site, 0, site_dir)
                else:
                    ws_out = await write_haproxy_backend(ssh, site, 0)
            _log(f"Web server config: {(ws_out or 'ok').strip()[:200]}")

            session.add(target_dep)
            await session.commit()

            if migration.source_deployment_id:
                source_dep = await session.get(SiteDeployment, migration.source_deployment_id)
                if source_dep and source_dep.directory:
                    source_server = await session.get(Server, source_dep.server_id)
                    if source_server and source_server.machine_id:
                        source_machine = await session.get(Machine, source_server.machine_id)
                        if source_machine:
                            _log(f"Rsyncing from {source_machine.ip}:{source_dep.directory}")
                            try:
                                rsync_out = await _best_effort_rsync(
                                    ssh, source_machine.ip, source_dep.directory, site_dir
                                )
                                _log(f"rsync: {rsync_out[:300]}")
                            except Exception as exc:
                                _log(f"rsync failed (non-fatal): {exc}")

        target_dep.status = "active"
        session.add(target_dep)

        if migration.source_deployment_id:
            source_dep = await session.get(SiteDeployment, migration.source_deployment_id)
            if source_dep:
                source_dep.status = "retired"
                source_dep.retired_at = _utcnow()
                session.add(source_dep)
                _log(f"Retired source deployment id={source_dep.id}")

        migration.status = "succeeded"
        migration.completed_at = _utcnow()
        _log("Migration succeeded.")

    except Exception as exc:
        migration.status = "failed"
        migration.completed_at = _utcnow()
        migration.error_message = str(exc)[:1000]
        _log(f"FAILED: {exc}")

    migration.log = "\n".join(log_lines)
    session.add(migration)
    await session.commit()

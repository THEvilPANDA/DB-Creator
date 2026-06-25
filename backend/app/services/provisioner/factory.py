from contextlib import asynccontextmanager
from urllib.parse import urlparse, urlunparse
from app.services.provisioner.base import DatabaseProvisioner


def _rewrite_dsn(dsn: str, host: str, port: int) -> str:
    parsed = urlparse(dsn)
    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, _ = netloc.rsplit("@", 1)
        new_netloc = f"{userinfo}@{host}:{port}"
    else:
        new_netloc = f"{host}:{port}"
    return urlunparse(parsed._replace(netloc=new_netloc))


def _build_provisioner(server, dsn: str) -> DatabaseProvisioner:
    engine = server.engine
    api_key = getattr(server, "api_key", None)
    sid = server.id
    warn = server.warning_threshold_pct
    crit = server.critical_threshold_pct
    match engine:
        case "postgresql":
            from app.services.provisioner.postgresql import PostgreSQLProvisioner
            return PostgreSQLProvisioner(dsn=dsn, server_id=sid,
                                        warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "pgvector":
            from app.services.provisioner.pgvector import PgvectorProvisioner
            return PgvectorProvisioner(dsn=dsn, server_id=sid,
                                      warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mysql":
            from app.services.provisioner.mysql import MySQLProvisioner
            return MySQLProvisioner(dsn=dsn, server_id=sid,
                                   warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mongodb":
            from app.services.provisioner.mongodb import MongoDBProvisioner
            return MongoDBProvisioner(dsn=dsn, server_id=sid,
                                     warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "qdrant":
            from app.services.provisioner.qdrant import QdrantProvisioner
            return QdrantProvisioner(base_url=dsn, api_key=api_key, server_id=sid,
                                    warning_threshold_pct=warn, critical_threshold_pct=crit)
        case _:
            raise ValueError(f"Unknown engine: {engine!r}")


@asynccontextmanager
async def get_provisioner(server, session=None):
    admin_dsn = server.admin_dsn or ""
    if server.machine_id and session:
        from app.models.machine import Machine
        from app.models.ssh_key import SSHKey
        from app.services.encryption import decrypt
        from app.services.ssh_tunnel import open_tunnel
        machine = await session.get(Machine, server.machine_id)
        if not machine or machine.is_deleted:
            raise ValueError(f"Machine {server.machine_id} not found")
        ssh_key_rec = await session.get(SSHKey, machine.ssh_key_id)
        if not ssh_key_rec:
            raise ValueError(f"SSH key {machine.ssh_key_id} not found")
        key_material = decrypt(ssh_key_rec.encrypted_private_key)
        passphrase = decrypt(ssh_key_rec.passphrase_encrypted) if ssh_key_rec.passphrase_encrypted else None
        async with open_tunnel(
            host=machine.ip,
            ssh_port=machine.ssh_port,
            username=ssh_key_rec.username,
            key_material=key_material,
            db_port=server.port,
            passphrase=passphrase,
        ) as local_port:
            tunneled_dsn = _rewrite_dsn(admin_dsn, "127.0.0.1", local_port)
            yield _build_provisioner(server, tunneled_dsn)
    else:
        yield _build_provisioner(server, admin_dsn)

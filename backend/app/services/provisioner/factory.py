from app.services.provisioner.base import DatabaseProvisioner


def get_provisioner(server) -> DatabaseProvisioner:
    engine = server.engine
    admin_dsn = server.admin_dsn or ""
    api_key = getattr(server, "api_key", None)
    sid = server.id
    warn = server.warning_threshold_pct
    crit = server.critical_threshold_pct

    match engine:
        case "postgresql":
            from app.services.provisioner.postgresql import PostgreSQLProvisioner
            return PostgreSQLProvisioner(dsn=admin_dsn, server_id=sid,
                                        warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "pgvector":
            from app.services.provisioner.pgvector import PgvectorProvisioner
            return PgvectorProvisioner(dsn=admin_dsn, server_id=sid,
                                       warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mysql":
            from app.services.provisioner.mysql import MySQLProvisioner
            return MySQLProvisioner(dsn=admin_dsn, server_id=sid,
                                    warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "mongodb":
            from app.services.provisioner.mongodb import MongoDBProvisioner
            return MongoDBProvisioner(dsn=admin_dsn, server_id=sid,
                                      warning_threshold_pct=warn, critical_threshold_pct=crit)
        case "qdrant":
            from app.services.provisioner.qdrant import QdrantProvisioner
            return QdrantProvisioner(base_url=admin_dsn, api_key=api_key, server_id=sid,
                                     warning_threshold_pct=warn, critical_threshold_pct=crit)
        case _:
            raise ValueError(f"Unknown engine: {engine!r}")

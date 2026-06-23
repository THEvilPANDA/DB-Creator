import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.database import AsyncSessionLocal
from app.models.creation_log import CreationLog
from app.models.database_template import DatabaseTemplate
from app.models.job import Job
from app.models.server import Server
from app.services.events import DomainEvent, publisher
from app.services.iac import generate_terraform, generate_yaml
from app.services.provisioner.base import DatabaseSpec, PermissionSpec, UserSpec
from app.services.provisioner.postgresql import PostgreSQLProvisioner


def _dsn_user(dsn: str) -> str:
    """Extract the username from a DSN string."""
    parsed = urlparse(dsn)
    return parsed.username or "postgres"


async def provision_database(ctx: dict, job_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            return {"success": False, "error": "Job not found"}

        # Validate prerequisites
        if not job.server_id:
            await _fail(session, job, "No server assigned to this job")
            return {"success": False, "error": "No server assigned"}

        server: Server | None = await session.get(Server, job.server_id)
        if not server or not server.admin_dsn:
            await _fail(session, job, "Server not found or has no admin_dsn — cannot provision")
            return {"success": False, "error": "Server missing credentials"}

        db_template: DatabaseTemplate | None = (
            await session.get(DatabaseTemplate, job.db_template_id) if job.db_template_id else None
        )

        # Mark running
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.add(job)
        await session.commit()
        publisher.publish(DomainEvent("DatabaseProvisioningStarted", {"job_id": job_id}))

        try:
            provisioner = PostgreSQLProvisioner(
                dsn=server.admin_dsn,
                server_id=server.id,
                warning_threshold_pct=server.warning_threshold_pct,
                critical_threshold_pct=server.critical_threshold_pct,
            )

            extensions: list[str] = db_template.extensions if db_template else []
            privileges: list[str] = ["CONNECT", "USAGE", "CREATE"]
            if db_template and db_template.permissions:
                app_privs = db_template.permissions.get("app_user")
                if app_privs:
                    privileges = app_privs

            db_user = f"{job.db_name}_user"
            db_password = secrets.token_urlsafe(24)

            # Order matters: create user → create DB owned by user → grant → extensions
            user_result = await provisioner.create_user(
                UserSpec(username=db_user, password=db_password, db_name=job.db_name)
            )
            if not user_result.success:
                raise RuntimeError(f"create_user failed: {user_result.message}")

            db_result = await provisioner.create_database(
                DatabaseSpec(name=job.db_name, owner=db_user, extensions=[])
            )
            if not db_result.success:
                raise RuntimeError(f"create_database failed: {db_result.message}")

            await provisioner.grant_permissions(
                PermissionSpec(db_name=job.db_name, username=db_user, privileges=privileges)
            )

            if extensions:
                await provisioner.enable_extensions(job.db_name, extensions)

            connection_uri = (
                f"postgresql://{db_user}:{db_password}@{server.host}:{server.port}/{job.db_name}"
            )

            log = CreationLog(
                job_id=job.id,
                server_id=server.id,
                db_name=job.db_name,
                db_user=db_user,
                connection_uri=connection_uri,
                iac_yaml=generate_yaml(
                    db_name=job.db_name,
                    db_user=db_user,
                    host=server.host,
                    port=server.port,
                    environment=job.environment,
                    engine=server.engine,
                ),
                iac_terraform=generate_terraform(
                    db_name=job.db_name,
                    db_user=db_user,
                    host=server.host,
                    port=server.port,
                ),
                provisioned_at=datetime.now(timezone.utc),
            )
            session.add(log)

            job.status = "succeeded"
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            await session.commit()

            publisher.publish(DomainEvent(
                "DatabaseProvisioningCompleted",
                {"job_id": job_id, "db_name": job.db_name, "db_user": db_user},
            ))
            return {"success": True, "job_id": job_id, "db_name": job.db_name}

        except Exception as exc:
            await _fail(session, job, str(exc)[:1000])
            publisher.publish(DomainEvent(
                "DatabaseProvisioningFailed", {"job_id": job_id, "error": str(exc)}
            ))
            return {"success": False, "error": str(exc)}


async def _fail(session, job: Job, message: str) -> None:
    job.status = "failed"
    job.error_message = message
    job.completed_at = datetime.now(timezone.utc)
    session.add(job)
    await session.commit()

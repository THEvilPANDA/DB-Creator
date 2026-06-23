from datetime import datetime, timezone

from app.database import AsyncSessionLocal
from app.models.job import Job
from app.services.events import DomainEvent, publisher


async def provision_database(ctx: dict, job_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            return {"success": False, "error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.add(job)
        await session.commit()

        publisher.publish(DomainEvent("DatabaseProvisioningStarted", {"job_id": job_id}))

        try:
            # Provisioner wired in Phase 3 when server credentials are stored.
            # Phase 0: mark succeeded to demonstrate the task pipeline end-to-end.
            job.status = "succeeded"
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            await session.commit()
            publisher.publish(DomainEvent("DatabaseProvisioningCompleted", {"job_id": job_id}))
            return {"success": True, "job_id": job_id}
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            await session.commit()
            publisher.publish(DomainEvent("DatabaseProvisioningFailed", {"job_id": job_id, "error": str(exc)}))
            return {"success": False, "error": str(exc)}

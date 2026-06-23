import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.approval import ApprovalRequest
from app.models.job import Job
from app.models.server import Server
from app.schemas.approval import ApprovalDecide, ApprovalRead
from app.schemas.job import JobCreate, JobRead
from app.services.approval import ApprovalService
from app.services.capacity import CapacityService
from app.services.events import DomainEvent, publisher
from app.services.placement import PlacementService
from app.services.provisioner.postgresql import PostgreSQLProvisioner

router = APIRouter(prefix="/jobs", tags=["jobs"])
_approval_svc = ApprovalService()
_capacity_svc = CapacityService()
_placement_svc = PlacementService()


async def _get_capacity(server: Server):
    from app.services.provisioner.base import CapacityMetrics
    if not server.admin_dsn:
        return CapacityMetrics(server.id, 0, 0, 0.0, 0.0, server.warning_threshold_pct, server.critical_threshold_pct)
    try:
        p = PostgreSQLProvisioner(
            dsn=server.admin_dsn,
            server_id=server.id,
            warning_threshold_pct=server.warning_threshold_pct,
            critical_threshold_pct=server.critical_threshold_pct,
        )
        return await asyncio.wait_for(p.get_capacity(), timeout=5.0)
    except Exception:
        from app.services.provisioner.base import CapacityMetrics
        return CapacityMetrics(server.id, 0, 0, 0.0, 0.0, server.warning_threshold_pct, server.critical_threshold_pct)


@router.post("", response_model=JobRead, status_code=201)
async def submit_job(payload: JobCreate, session: AsyncSession = Depends(get_session)):
    # Resolve target server
    target_server: Server | None = None

    if payload.server_id:
        target_server = await session.get(Server, payload.server_id)
        if not target_server or target_server.is_deleted or not target_server.is_active:
            raise HTTPException(422, "Server not found or inactive")
    else:
        # Auto-select via environment_default placement
        result = await session.execute(
            select(Server).where(Server.is_deleted == False, Server.is_active == True)  # noqa: E712
        )
        all_servers = result.scalars().all()
        target_server = _placement_svc.select(
            list(all_servers), strategy="environment_default", environment=payload.environment
        )

    # Capacity gate — only check if we have a server and it has credentials
    if target_server:
        metrics = await _get_capacity(target_server)
        if not _capacity_svc.is_accepting_jobs(target_server, metrics):
            raise HTTPException(422, f"Server '{target_server.name}' is not accepting jobs (health={metrics.health})")

    db_name = payload.db_name or f"db_{int(datetime.now(timezone.utc).timestamp())}"
    job = Job(
        db_name=db_name,
        environment=payload.environment,
        owner=payload.owner,
        team=payload.team,
        cost_center=payload.cost_center,
        server_id=target_server.id if target_server else payload.server_id,
        naming_profile_id=payload.naming_profile_id,
        db_template_id=payload.db_template_id,
        request_template_id=payload.request_template_id,
        expires_at=payload.expires_at,
        status="pending",
    )
    session.add(job)
    await session.flush()

    auto_approved = _approval_svc.is_auto_approved(payload.environment)
    approval = ApprovalRequest(
        job_id=job.id,
        status="approved" if auto_approved else "pending",
        approver="system" if auto_approved else None,
        decided_at=datetime.now(timezone.utc) if auto_approved else None,
    )
    session.add(approval)

    if auto_approved:
        job.status = "queued"

    await session.commit()
    await session.refresh(job)

    publisher.publish(DomainEvent("DatabaseRequested", {"job_id": job.id, "environment": job.environment}))
    return job


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: int, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job or job.is_deleted:
        raise HTTPException(404, "Job not found")
    return job


@router.delete("/{job_id}", response_model=JobRead)
async def cancel_job(job_id: int, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job or job.is_deleted:
        raise HTTPException(404, "Job not found")
    if job.status in ("succeeded", "failed"):
        raise HTTPException(400, f"Cannot cancel a job with status '{job.status}'")
    job.status = "cancelled"
    job.is_deleted = True
    job.deleted_at = datetime.now(timezone.utc)
    job.deleted_by = "system"
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@router.post("/{job_id}/approve", response_model=ApprovalRead)
async def decide_approval(
    job_id: int,
    payload: ApprovalDecide,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApprovalRequest).where(ApprovalRequest.job_id == job_id)
    )
    approval = result.scalars().first()
    if not approval:
        raise HTTPException(404, "Approval request not found")
    if approval.status != "pending":
        raise HTTPException(400, f"Approval already decided: {approval.status}")

    approval.status = payload.status
    approval.approver = "system"  # Phase 7: replace with authenticated principal
    approval.comments = payload.comments
    approval.decided_at = datetime.now(timezone.utc)
    session.add(approval)

    if payload.status == "approved":
        job = await session.get(Job, job_id)
        if job:
            job.status = "queued"
            session.add(job)

    await session.commit()
    await session.refresh(approval)
    return approval

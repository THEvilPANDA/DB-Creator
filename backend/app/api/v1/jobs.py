import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.approval import ApprovalRequest
from app.models.job import Job
from app.models.naming_profile import NamingProfile
from app.models.request_template import RequestTemplate
from app.models.server import Server
from app.schemas.approval import ApprovalDecide, ApprovalRead
from app.schemas.job import JobCreate, JobRead
from app.services.approval import ApprovalService
from app.services.capacity import CapacityService
from app.services.events import DomainEvent, publisher
from app.services.naming import NamingService
from app.services.placement import PlacementService
from app.services.provisioner.postgresql import PostgreSQLProvisioner

router = APIRouter(prefix="/jobs", tags=["jobs"])
_approval_svc = ApprovalService()
_capacity_svc = CapacityService()
_placement_svc = PlacementService()
_naming_svc = NamingService()


async def _get_base_capacity(server: Server):
    from app.services.provisioner.base import CapacityMetrics
    if not server.admin_dsn:
        return CapacityMetrics(server.id, 0, 0, 0.0, 0.0,
                               server.warning_threshold_pct, server.critical_threshold_pct)
    try:
        p = PostgreSQLProvisioner(dsn=server.admin_dsn, server_id=server.id,
                                  warning_threshold_pct=server.warning_threshold_pct,
                                  critical_threshold_pct=server.critical_threshold_pct)
        return await asyncio.wait_for(p.get_capacity(), timeout=5.0)
    except Exception:
        from app.services.provisioner.base import CapacityMetrics
        return CapacityMetrics(server.id, 0, 0, 0.0, 0.0,
                               server.warning_threshold_pct, server.critical_threshold_pct)


@router.post("", response_model=JobRead, status_code=201)
async def submit_job(payload: JobCreate, session: AsyncSession = Depends(get_session)):
    # Work with a mutable copy so we can apply template overrides
    p = payload.model_dump()

    # ── 1. Apply request template (fills in blanks; caller values win) ──────────
    if p.get("request_template_id"):
        tmpl = await session.get(RequestTemplate, p["request_template_id"])
        if not tmpl or tmpl.is_deleted:
            raise HTTPException(422, "Request template not found")
        if not p.get("environment"):
            p["environment"] = tmpl.environment
        if not p.get("db_template_id"):
            p["db_template_id"] = tmpl.db_template_id
        if not p.get("naming_profile_id"):
            p["naming_profile_id"] = tmpl.naming_profile_id
        if not p.get("cost_center"):
            p["cost_center"] = tmpl.cost_center
        if not p.get("team"):
            p["team"] = tmpl.team
        if not p.get("expires_at") and tmpl.expiration_days:
            p["expires_at"] = datetime.now(timezone.utc) + timedelta(days=tmpl.expiration_days)

    # ── 2. Resolve target server ─────────────────────────────────────────────────
    target_server: Server | None = None
    if p.get("server_id"):
        target_server = await session.get(Server, p["server_id"])
        if not target_server or target_server.is_deleted or not target_server.is_active:
            raise HTTPException(422, "Server not found or inactive")
    else:
        result = await session.execute(
            select(Server).where(Server.is_deleted == False, Server.is_active == True)  # noqa: E712
        )
        target_server = _placement_svc.select(
            list(result.scalars().all()),
            strategy="environment_default",
            environment=p.get("environment"),
        )

    # ── 3. Capacity gate ─────────────────────────────────────────────────────────
    if target_server:
        metrics = await _get_base_capacity(target_server)
        if not _capacity_svc.is_accepting_jobs(target_server, metrics):
            raise HTTPException(
                422,
                f"Server '{target_server.name}' is not accepting jobs (health={metrics.health})"
            )

    # ── 4. Resolve database name via naming profile ──────────────────────────────
    db_name: str
    if p.get("naming_profile_id"):
        profile = await session.get(NamingProfile, p["naming_profile_id"])
        if not profile or profile.is_deleted:
            raise HTTPException(422, "Naming profile not found")

        context = {
            "owner": p.get("owner") or "",
            "team": p.get("team") or "",
            "environment": p.get("environment") or "",
            "db_name": p.get("db_name") or "",
        }

        check_exists = None
        if target_server and target_server.admin_dsn:
            prov = PostgreSQLProvisioner(
                dsn=target_server.admin_dsn,
                server_id=target_server.id,
                warning_threshold_pct=target_server.warning_threshold_pct,
                critical_threshold_pct=target_server.critical_threshold_pct,
            )
            check_exists = prov.database_exists

        try:
            db_name = await _naming_svc.generate(profile, context, check_exists)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    else:
        raw = p.get("db_name") or f"db_{int(datetime.now(timezone.utc).timestamp())}"
        db_name = raw

    # ── 5. Create Job + ApprovalRequest ─────────────────────────────────────────
    job = Job(
        db_name=db_name,
        environment=p.get("environment", "development"),
        owner=p.get("owner", ""),
        team=p.get("team"),
        cost_center=p.get("cost_center"),
        server_id=target_server.id if target_server else p.get("server_id"),
        naming_profile_id=p.get("naming_profile_id"),
        db_template_id=p.get("db_template_id"),
        request_template_id=p.get("request_template_id"),
        expires_at=p.get("expires_at"),
        status="pending",
    )
    session.add(job)
    await session.flush()

    auto_approved = _approval_svc.is_auto_approved(job.environment)
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

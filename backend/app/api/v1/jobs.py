import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import AsyncSessionLocal, get_session
from app.dependencies import get_arq
from app.models.approval import ApprovalRequest
from app.models.creation_log import CreationLog
from app.models.job import Job
from app.models.naming_profile import NamingProfile
from app.models.request_template import RequestTemplate
from app.models.server import Server
from app.schemas.approval import ApprovalDecide, ApprovalRead
from app.schemas.job import JobCreate, JobRead
from app.metrics import JOBS_SUBMITTED
from app.services.approval import ApprovalService
from app.services.audit import write_audit
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

_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})


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
async def submit_job(
    payload: JobCreate,
    session: AsyncSession = Depends(get_session),
    arq=Depends(get_arq),
):
    p = payload.model_dump()

    # ── 1. Request template auto-fill ───────────────────────────────────────────
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

    # ── 4. Naming profile resolution ─────────────────────────────────────────────
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
            prov = PostgreSQLProvisioner(dsn=target_server.admin_dsn, server_id=target_server.id,
                                         warning_threshold_pct=target_server.warning_threshold_pct,
                                         critical_threshold_pct=target_server.critical_threshold_pct)
            check_exists = prov.database_exists
        try:
            db_name = await _naming_svc.generate(profile, context, check_exists)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    else:
        db_name = p.get("db_name") or f"db_{int(datetime.now(timezone.utc).timestamp())}"

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

    await write_audit(session, actor="system", action="job.submit", entity_type="job",
                      entity_id=job.id, payload={"environment": job.environment, "db_name": job.db_name,
                                                   "auto_approved": auto_approved})
    await session.commit()
    await session.refresh(job)

    JOBS_SUBMITTED.labels(environment=job.environment).inc()
    publisher.publish(DomainEvent("DatabaseRequested", {"job_id": job.id, "environment": job.environment}))

    if auto_approved and arq:
        await arq.enqueue_job("provision_database", job_id=job.id)

    return job


@router.get("/{job_id}/events")
async def job_events(job_id: int):
    """Stream job status changes via Server-Sent Events (text/event-stream)."""
    async def generate():
        last_status = None
        for _ in range(300):  # 5-minute max stream
            async with AsyncSessionLocal() as s:
                job = await s.get(Job, job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                return
            if job.status != last_status:
                last_status = job.status
                payload = {"status": job.status, "job_id": job_id, "db_name": job.db_name}
                if job.status == "failed":
                    payload["error"] = True  # raw error_message withheld; use GET /jobs/{id}
                yield f"data: {json.dumps(payload)}\n\n"
            if job.status in _TERMINAL:
                yield "event: done\ndata: {}\n\n"
                return
            await asyncio.sleep(1)
        yield f"data: {json.dumps({'error': 'stream timeout after 5 minutes'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/connection")
async def job_connection(job_id: int, session: AsyncSession = Depends(get_session)):
    """Return connection details and IaC snippets for a successfully provisioned job.

    SECURITY (Phase 7): restrict to authenticated owner or admin via get_current_user.
    Currently unprotected — deploy behind a network boundary until auth is added.
    """
    job = await session.get(Job, job_id)
    if not job or job.is_deleted:
        raise HTTPException(404, "Job not found")
    if job.status != "succeeded":
        raise HTTPException(409, f"Job is not succeeded (status: {job.status})")

    result = await session.execute(
        select(CreationLog).where(CreationLog.job_id == job_id)
    )
    log = result.scalars().first()
    if not log:
        raise HTTPException(404, "Connection details not yet available")

    await write_audit(session, actor="system", action="job.connection_accessed",
                      entity_type="job", entity_id=job_id,
                      payload={"db_name": log.db_name, "db_user": log.db_user})
    await session.commit()

    return {
        "db_name": log.db_name,
        "db_user": log.db_user,
        "connection_uri": log.connection_uri,
        "env_vars": {
            "DB_NAME": log.db_name,
            "DB_USER": log.db_user or "",
            "DB_HOST": log.connection_uri.split("@")[1].rsplit("/", 1)[0] if log.connection_uri else "",
            "DB_PORT": "5432",
            "DATABASE_URL": log.connection_uri or "",
        },
        "iac_yaml": log.iac_yaml,
        "iac_terraform": log.iac_terraform,
    }


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
    await write_audit(session, actor="system", action="job.cancel", entity_type="job",
                      entity_id=job_id, payload={"previous_status": job.status})
    await session.commit()
    await session.refresh(job)
    return job


@router.post("/{job_id}/approve", response_model=ApprovalRead)
async def decide_approval(
    job_id: int,
    payload: ApprovalDecide,
    session: AsyncSession = Depends(get_session),
    arq=Depends(get_arq),
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
    await write_audit(session, actor="system", action=f"approval.{payload.status}",
                      entity_type="job", entity_id=job_id,
                      payload={"approval_id": approval.id, "comments": payload.comments})

    if payload.status == "approved":
        job = await session.get(Job, job_id)
        if job:
            job.status = "queued"
            session.add(job)
            await session.commit()
            if arq:
                await arq.enqueue_job("provision_database", job_id=job.id)
    else:
        await session.commit()

    await session.refresh(approval)
    return approval

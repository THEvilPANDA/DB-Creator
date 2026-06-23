from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.database import get_session
from app.models.creation_log import CreationLog
from app.models.job import Job
from app.models.server import Server

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Aggregate stats for the dashboard — job counts, server counts, history total."""
    by_status_rows = (
        await session.execute(
            select(Job.status, func.count(Job.id))
            .where(Job.is_deleted == False)  # noqa: E712
            .group_by(Job.status)
        )
    ).all()

    by_env_rows = (
        await session.execute(
            select(Job.environment, func.count(Job.id))
            .where(Job.is_deleted == False)  # noqa: E712
            .group_by(Job.environment)
        )
    ).all()

    server_total = (
        await session.execute(
            select(func.count(Server.id)).where(Server.is_deleted == False)  # noqa: E712
        )
    ).scalar_one()

    active_servers = (
        await session.execute(
            select(func.count(Server.id)).where(
                Server.is_deleted == False, Server.is_active == True  # noqa: E712
            )
        )
    ).scalar_one()

    total_provisioned = (
        await session.execute(
            select(func.count(CreationLog.id)).where(
                CreationLog.is_deleted == False  # noqa: E712
            )
        )
    ).scalar_one()

    by_status = dict(by_status_rows)
    by_environment = dict(by_env_rows)
    total_jobs = sum(by_status.values())
    succeeded = by_status.get("succeeded", 0)
    success_rate = round(succeeded / total_jobs * 100, 1) if total_jobs else 0.0

    return {
        "jobs": {
            "total": total_jobs,
            "by_status": by_status,
            "by_environment": by_environment,
            "success_rate_pct": success_rate,
        },
        "servers": {
            "total": server_total,
            "active": active_servers,
        },
        "history": {
            "total_provisioned": total_provisioned,
        },
    }

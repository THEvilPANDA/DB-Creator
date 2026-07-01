from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.dependencies import require_admin
from app.models.database_template import DatabaseTemplate
from app.models.job import Job
from app.models.server import Server

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(require_admin)])

SearchType = Literal["all", "jobs", "servers", "templates"]


@router.get("")
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    type: SearchType = "all",
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Full-text search across jobs, servers, and database templates."""
    pattern = f"%{q}%"
    result: dict = {}

    if type in ("all", "jobs"):
        rows = (
            await session.execute(
                select(Job)
                .where(
                    Job.is_deleted == False,  # noqa: E712
                    or_(
                        Job.db_name.ilike(pattern),
                        Job.owner.ilike(pattern),
                        Job.team.ilike(pattern),
                        Job.cost_center.ilike(pattern),
                    ),
                )
                .order_by(Job.id.desc())
                .limit(limit)
            )
        ).scalars().all()
        result["jobs"] = [
            {"id": j.id, "db_name": j.db_name, "owner": j.owner,
             "environment": j.environment, "status": j.status}
            for j in rows
        ]

    if type in ("all", "servers"):
        rows = (
            await session.execute(
                select(Server)
                .where(
                    Server.is_deleted == False,  # noqa: E712
                    or_(
                        Server.name.ilike(pattern),
                        Server.host.ilike(pattern),
                        Server.environment.ilike(pattern),
                    ),
                )
                .limit(limit)
            )
        ).scalars().all()
        result["servers"] = [
            {"id": s.id, "name": s.name, "host": s.host,
             "environment": s.environment, "is_active": s.is_active}
            for s in rows
        ]

    if type in ("all", "templates"):
        rows = (
            await session.execute(
                select(DatabaseTemplate)
                .where(
                    DatabaseTemplate.is_deleted == False,  # noqa: E712
                    or_(
                        DatabaseTemplate.name.ilike(pattern),
                        DatabaseTemplate.engine.ilike(pattern),
                    ),
                )
                .limit(limit)
            )
        ).scalars().all()
        result["templates"] = [
            {"id": t.id, "name": t.name, "engine": t.engine}
            for t in rows
        ]

    return result

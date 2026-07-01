from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.database import get_session
from app.dependencies import require_admin
from app.models.creation_log import CreationLog
from app.models.job import Job
from app.schemas.common import PaginatedResponse
from app.schemas.creation_log import CreationLogRead

router = APIRouter(prefix="/history", tags=["history"], dependencies=[Depends(require_admin)])


@router.get("", response_model=PaginatedResponse[CreationLogRead])
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    environment: Optional[str] = None,
    status: Optional[str] = None,
    server_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    base_stmt = (
        select(CreationLog)
        .where(CreationLog.is_deleted == False)  # noqa: E712
        .order_by(CreationLog.provisioned_at.desc())
    )

    if environment or status:
        base_stmt = base_stmt.join(Job, CreationLog.job_id == Job.id)
        if environment:
            base_stmt = base_stmt.where(Job.environment == environment)
        if status:
            base_stmt = base_stmt.where(Job.status == status)

    if server_id is not None:
        base_stmt = base_stmt.where(CreationLog.server_id == server_id)

    count_result = await session.execute(
        select(func.count()).select_from(base_stmt.subquery())
    )
    total = count_result.scalar_one()

    result = await session.execute(
        base_stmt.offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

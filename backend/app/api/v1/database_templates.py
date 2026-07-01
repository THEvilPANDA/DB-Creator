from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.dependencies import require_admin
from app.models.database_template import DatabaseTemplate
from app.schemas.database_template import DatabaseTemplateCreate, DatabaseTemplateRead, DatabaseTemplateUpdate

router = APIRouter(prefix="/database-templates", tags=["database-templates"], dependencies=[Depends(require_admin)])


@router.post("", response_model=DatabaseTemplateRead, status_code=201)
async def create_database_template(payload: DatabaseTemplateCreate, session: AsyncSession = Depends(get_session)):
    obj = DatabaseTemplate(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[DatabaseTemplateRead])
async def list_database_templates(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(DatabaseTemplate).where(DatabaseTemplate.is_deleted == False))  # noqa: E712
    return result.scalars().all()


@router.get("/{template_id}", response_model=DatabaseTemplateRead)
async def get_database_template(template_id: int, session: AsyncSession = Depends(get_session)):
    obj = await session.get(DatabaseTemplate, template_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Database template not found")
    return obj


@router.put("/{template_id}", response_model=DatabaseTemplateRead)
async def update_database_template(
    template_id: int,
    payload: DatabaseTemplateUpdate,
    session: AsyncSession = Depends(get_session),
):
    obj = await session.get(DatabaseTemplate, template_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Database template not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.delete("/{template_id}", response_model=DatabaseTemplateRead)
async def delete_database_template(template_id: int, session: AsyncSession = Depends(get_session)):
    obj = await session.get(DatabaseTemplate, template_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Database template not found")
    obj.is_deleted = True
    obj.deleted_at = datetime.now(timezone.utc)
    obj.deleted_by = "system"
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

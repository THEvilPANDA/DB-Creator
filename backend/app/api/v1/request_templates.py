from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.dependencies import require_admin
from app.models.request_template import RequestTemplate
from app.schemas.request_template import RequestTemplateCreate, RequestTemplateRead, RequestTemplateUpdate

router = APIRouter(prefix="/request-templates", tags=["request-templates"], dependencies=[Depends(require_admin)])


@router.post("", response_model=RequestTemplateRead, status_code=201)
async def create_request_template(payload: RequestTemplateCreate, session: AsyncSession = Depends(get_session)):
    obj = RequestTemplate(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[RequestTemplateRead])
async def list_request_templates(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(RequestTemplate).where(RequestTemplate.is_deleted == False))  # noqa: E712
    return result.scalars().all()


@router.get("/{template_id}", response_model=RequestTemplateRead)
async def get_request_template(template_id: int, session: AsyncSession = Depends(get_session)):
    obj = await session.get(RequestTemplate, template_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Request template not found")
    return obj


@router.put("/{template_id}", response_model=RequestTemplateRead)
async def update_request_template(
    template_id: int,
    payload: RequestTemplateUpdate,
    session: AsyncSession = Depends(get_session),
):
    obj = await session.get(RequestTemplate, template_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Request template not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.delete("/{template_id}", response_model=RequestTemplateRead)
async def delete_request_template(template_id: int, session: AsyncSession = Depends(get_session)):
    obj = await session.get(RequestTemplate, template_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Request template not found")
    obj.is_deleted = True
    obj.deleted_at = datetime.now(timezone.utc)
    obj.deleted_by = "system"
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

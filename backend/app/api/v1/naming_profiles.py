from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.naming_profile import NamingProfile
from app.schemas.naming_profile import NamingProfileCreate, NamingProfileRead, NamingProfileUpdate

router = APIRouter(prefix="/naming-profiles", tags=["naming-profiles"])


@router.post("", response_model=NamingProfileRead, status_code=201)
async def create_naming_profile(payload: NamingProfileCreate, session: AsyncSession = Depends(get_session)):
    obj = NamingProfile(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[NamingProfileRead])
async def list_naming_profiles(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(NamingProfile).where(NamingProfile.is_deleted == False))  # noqa: E712
    return result.scalars().all()


@router.get("/{profile_id}", response_model=NamingProfileRead)
async def get_naming_profile(profile_id: int, session: AsyncSession = Depends(get_session)):
    obj = await session.get(NamingProfile, profile_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Naming profile not found")
    return obj


@router.put("/{profile_id}", response_model=NamingProfileRead)
async def update_naming_profile(
    profile_id: int,
    payload: NamingProfileUpdate,
    session: AsyncSession = Depends(get_session),
):
    obj = await session.get(NamingProfile, profile_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Naming profile not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.delete("/{profile_id}", response_model=NamingProfileRead)
async def delete_naming_profile(profile_id: int, session: AsyncSession = Depends(get_session)):
    obj = await session.get(NamingProfile, profile_id)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Naming profile not found")
    obj.is_deleted = True
    obj.deleted_at = datetime.now(timezone.utc)
    obj.deleted_by = "system"
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

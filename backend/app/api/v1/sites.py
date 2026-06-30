from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.site import Site, SiteDeployment, SiteMigration
from app.schemas.site import (
    MigrationCreate,
    MigrationRead,
    SiteCreate,
    SiteDeploymentRead,
    SiteRead,
    SiteUpdate,
)
from app.services.audit import write_audit
from app.services.site_migration import run_migration

router = APIRouter(prefix="/sites", tags=["sites"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("", response_model=SiteRead, status_code=201)
async def create_site(payload: SiteCreate, session: AsyncSession = Depends(get_session)):
    site = Site(**payload.model_dump())
    session.add(site)
    await session.commit()
    await session.refresh(site)
    await write_audit(session, "system", "create", "site", site.id, payload.model_dump())
    await session.commit()
    return SiteRead.model_validate(site)


@router.get("", response_model=list[SiteRead])
async def list_sites(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Site).where(Site.is_deleted == False))  # noqa: E712
    return [SiteRead.model_validate(s) for s in result.scalars().all()]


@router.get("/migrations/{migration_id}", response_model=MigrationRead)
async def get_migration(migration_id: int, session: AsyncSession = Depends(get_session)):
    migration = await session.get(SiteMigration, migration_id)
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")
    return MigrationRead.model_validate(migration)


@router.get("/{site_id}", response_model=SiteRead)
async def get_site(site_id: int, session: AsyncSession = Depends(get_session)):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteRead.model_validate(site)


@router.put("/{site_id}", response_model=SiteRead)
async def update_site(
    site_id: int,
    payload: SiteUpdate,
    session: AsyncSession = Depends(get_session),
):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(site, key, value)
    site.updated_at = _utcnow()
    session.add(site)
    await session.commit()
    await session.refresh(site)
    await write_audit(session, "system", "update", "site", site.id, payload.model_dump(exclude_none=True))
    await session.commit()
    return SiteRead.model_validate(site)


@router.delete("/{site_id}", response_model=SiteRead)
async def delete_site(site_id: int, session: AsyncSession = Depends(get_session)):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    site.is_deleted = True
    site.deleted_at = _utcnow()
    site.deleted_by = "system"
    session.add(site)
    await session.commit()
    await session.refresh(site)
    await write_audit(session, "system", "delete", "site", site.id)
    await session.commit()
    return SiteRead.model_validate(site)


@router.get("/{site_id}/deployments", response_model=list[SiteDeploymentRead])
async def list_deployments(site_id: int, session: AsyncSession = Depends(get_session)):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    result = await session.execute(
        select(SiteDeployment).where(SiteDeployment.site_id == site_id)
    )
    return [SiteDeploymentRead.model_validate(d) for d in result.scalars().all()]


@router.post("/{site_id}/migrate", response_model=MigrationRead, status_code=201)
async def start_migration(
    site_id: int,
    payload: MigrationCreate,
    session: AsyncSession = Depends(get_session),
):
    site = await session.get(Site, site_id)
    if not site or site.is_deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    if payload.site_id != site_id:
        raise HTTPException(status_code=400, detail="site_id in body must match URL")

    active_result = await session.execute(
        select(SiteDeployment)
        .where(SiteDeployment.site_id == site_id, SiteDeployment.status == "active")
        .order_by(SiteDeployment.id.desc())
        .limit(1)
    )
    source_dep = active_result.scalars().first()

    migration = SiteMigration(
        site_id=site_id,
        source_deployment_id=source_dep.id if source_dep else None,
        target_server_id=payload.target_server_id,
    )
    session.add(migration)
    await session.commit()
    await session.refresh(migration)

    await write_audit(session, "system", "migrate", "site", site_id, {
        "migration_id": migration.id,
        "target_server_id": payload.target_server_id,
    })
    await session.commit()

    await run_migration(session, migration)
    await session.refresh(migration)
    return MigrationRead.model_validate(migration)

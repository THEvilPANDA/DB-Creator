from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.server import Server
from app.schemas.server import CapacityMetrics, ServerCreate, ServerRead, ServerUpdate

router = APIRouter(prefix="/servers", tags=["servers"])


@router.post("", response_model=ServerRead, status_code=201)
async def create_server(payload: ServerCreate, session: AsyncSession = Depends(get_session)):
    server = Server(**payload.model_dump())
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


@router.get("", response_model=list[ServerRead])
async def list_servers(
    environment: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Server).where(Server.is_deleted == False)  # noqa: E712
    if environment:
        stmt = stmt.where(Server.environment == environment)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{server_id}", response_model=ServerRead)
async def get_server(server_id: int, session: AsyncSession = Depends(get_session)):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.put("/{server_id}", response_model=ServerRead)
async def update_server(
    server_id: int,
    payload: ServerUpdate,
    session: AsyncSession = Depends(get_session),
):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(server, key, value)
    server.updated_at = datetime.now(timezone.utc)
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


@router.delete("/{server_id}", response_model=ServerRead)
async def delete_server(server_id: int, session: AsyncSession = Depends(get_session)):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    server.is_deleted = True
    server.deleted_at = datetime.now(timezone.utc)
    server.deleted_by = "system"
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


@router.get("/{server_id}/capacity", response_model=CapacityMetrics)
async def get_server_capacity(server_id: int, session: AsyncSession = Depends(get_session)):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    return CapacityMetrics(
        server_id=server.id,
        db_count=0,
        active_connections=0,
        disk_used_gb=0.0,
        disk_free_gb=server.max_storage_gb,
        health="healthy",
    )

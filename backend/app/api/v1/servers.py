import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.dependencies import require_admin
from app.models.server import Server
from app.models.user import User
from app.schemas.server import (
    CapacityMetrics,
    HealthSummaryResponse,
    ServerCreate,
    ServerHealthEntry,
    ServerRead,
    ServerUpdate,
)
from app.services.provisioner.factory import get_provisioner
from app.api.v1.databases import (
    QueryRequest,
    QueryResponse,
    _run_pg_query,
    _run_mysql_query,
    _run_mongodb_query,
    _run_qdrant_query,
)

router = APIRouter(prefix="/servers", tags=["servers"], dependencies=[Depends(require_admin)])

import re as _re

def _assert_select_only(sql: str) -> None:
    """Raise 400 if sql contains anything other than SELECT/WITH/SHOW/EXPLAIN."""
    stripped = _re.sub(r'/\*.*?\*/', '', sql, flags=_re.DOTALL)  # strip block comments
    stripped = _re.sub(r'--[^\n]*', '', stripped)                  # strip line comments
    first_word = stripped.strip().split()[0].upper() if stripped.strip() else ''
    if first_word not in ('SELECT', 'WITH', 'SHOW', 'EXPLAIN', 'DESCRIBE', 'DESC'):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed in the SQL console")

_UNKNOWN_CAPACITY = lambda sid: CapacityMetrics(  # noqa: E731
    server_id=sid, db_count=0, active_connections=0,
    disk_used_gb=0.0, disk_free_gb=0.0, health="unknown",
)


async def _live_capacity(server: Server, session: AsyncSession) -> CapacityMetrics:
    if not server.admin_dsn:
        return _UNKNOWN_CAPACITY(server.id)
    try:
        async with get_provisioner(server, session) as provisioner:
            m = await asyncio.wait_for(provisioner.get_capacity(), timeout=5.0)
            return CapacityMetrics(
                server_id=m.server_id,
                db_count=m.db_count,
                active_connections=m.active_connections,
                disk_used_gb=m.disk_used_gb,
                disk_free_gb=m.disk_free_gb,
                health=m.health,
            )
    except Exception:
        return _UNKNOWN_CAPACITY(server.id)


@router.post("", response_model=ServerRead, status_code=201)
async def create_server(payload: ServerCreate, session: AsyncSession = Depends(get_session)):
    server = Server(**payload.model_dump())
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return ServerRead.model_validate(server)


@router.get("", response_model=list[ServerRead])
async def list_servers(
    environment: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Server).where(Server.is_deleted == False)  # noqa: E712
    if environment:
        stmt = stmt.where(Server.environment == environment)
    result = await session.execute(stmt)
    return [ServerRead.model_validate(s) for s in result.scalars().all()]


@router.get("/health-summary", response_model=HealthSummaryResponse)
async def health_summary(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Server).where(Server.is_deleted == False))  # noqa: E712
    servers = result.scalars().all()

    capacities = await asyncio.gather(*[_live_capacity(s, session) for s in servers])

    entries: list[ServerHealthEntry] = []
    counts = {"healthy": 0, "warning": 0, "critical": 0, "unknown": 0}
    for server, cap in zip(servers, capacities):
        h = cap.health if cap.health in counts else "unknown"
        counts[h] += 1
        entries.append(ServerHealthEntry(
            server_id=server.id,
            name=server.name,
            environment=server.environment,
            health=h,
            db_count=cap.db_count,
            active_connections=cap.active_connections,
            disk_used_gb=cap.disk_used_gb,
        ))

    return HealthSummaryResponse(servers=entries, **counts)


@router.get("/{server_id}", response_model=ServerRead)
async def get_server(server_id: int, session: AsyncSession = Depends(get_session)):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    return ServerRead.model_validate(server)


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
    server.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return ServerRead.model_validate(server)


@router.delete("/{server_id}", response_model=ServerRead)
async def delete_server(server_id: int, session: AsyncSession = Depends(get_session)):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    server.is_deleted = True
    server.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    server.deleted_by = "system"
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return ServerRead.model_validate(server)


@router.get("/{server_id}/capacity", response_model=CapacityMetrics)
async def get_server_capacity(server_id: int, session: AsyncSession = Depends(get_session)):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    return await _live_capacity(server, session)


@router.post("/{server_id}/query", response_model=QueryResponse)
async def query_server(
    server_id: int,
    payload: QueryRequest,
    _: "User" = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    server = await session.get(Server, server_id)
    if not server or server.is_deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    if not server.admin_dsn:
        raise HTTPException(
            status_code=400,
            detail="Server has no admin DSN — set it in the Servers page before querying",
        )

    _assert_select_only(payload.sql)
    engine = server.engine

    if engine in ("postgresql", "pgvector"):
        return await _run_pg_query(server.admin_dsn, payload.sql)

    elif engine == "mysql":
        import aiomysql
        from urllib.parse import urlparse
        parsed = urlparse(server.admin_dsn)
        try:
            conn = await aiomysql.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 3306,
                user=parsed.username or "root",
                password=parsed.password or "",
                db=parsed.path.lstrip("/") or None,
                autocommit=True,
            )
        except Exception:
            return QueryResponse(columns=[], rows=[], row_count=0, error="Cannot connect to MySQL")
        try:
            return await _run_mysql_query(conn, payload.sql)
        finally:
            conn.close()

    elif engine == "mongodb":
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(server.admin_dsn, serverSelectionTimeoutMS=5000)
        try:
            return await _run_mongodb_query(client, payload.sql)
        finally:
            client.close()

    elif engine == "qdrant":
        api_key = getattr(server, "api_key", None)
        return await _run_qdrant_query(server.admin_dsn, api_key, payload.sql)

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported engine: {engine!r}")

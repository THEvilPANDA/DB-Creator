import json
import logging
import re
from typing import Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user
from app.models.creation_log import CreationLog
from app.models.job import Job
from app.models.server import Server
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/databases", tags=["databases"])

_SELECT_RE = re.compile(r"^\s*(SELECT|WITH|TABLE|VALUES|EXPLAIN|SHOW)\b", re.IGNORECASE)
MAX_ROWS = 500


def _to_json(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    error: Optional[str] = None
    status: Optional[str] = None


async def _run_pg_query(dsn: str, sql: str) -> QueryResponse:
    try:
        conn = await asyncpg.connect(dsn, timeout=10)
    except Exception:
        logger.exception("Failed to connect (pg)")
        return QueryResponse(columns=[], rows=[], row_count=0, error="Cannot connect to database")
    try:
        records = await conn.fetch(sql)
        if not records:
            return QueryResponse(columns=[], rows=[], row_count=0)
        columns = list(records[0].keys())
        rows = [[_to_json(v) for v in r.values()] for r in records[:MAX_ROWS]]
        return QueryResponse(columns=columns, rows=rows, row_count=len(records))
    except asyncpg.PostgresError as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))
    except Exception:
        logger.exception("PG query failed")
        return QueryResponse(columns=[], rows=[], row_count=0, error="Query execution failed")
    finally:
        await conn.close()


async def _run_mysql_query(conn, sql: str) -> QueryResponse:
    try:
        await conn.execute(sql)
        if conn.description:
            columns = [d[0] for d in conn.description]
            rows_raw = await conn.fetchall()
            rows = [[_to_json(v) for v in row] for row in rows_raw[:MAX_ROWS]]
            return QueryResponse(columns=columns, rows=rows, row_count=len(rows_raw))
        else:
            status = f"Query OK, {conn.rowcount} row(s) affected"
            return QueryResponse(columns=["result"], rows=[[status]], row_count=1, status=status)
    except Exception as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))


async def _run_mongodb_query(client, payload_str: str) -> QueryResponse:
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        return QueryResponse(columns=[], rows=[], row_count=0,
                             error=f"Invalid JSON: {exc}. Format: {{\"op\":\"find\",\"coll\":\"name\",\"filter\":{{}}}}")
    op = payload.get("op", "find")
    db_name = payload.get("db")  # optional; defaults to the provisioned DB
    coll_name = payload.get("coll", "")
    try:
        if op == "list_collections":
            names = await client[db_name].list_collection_names()
            rows = [[n] for n in names]
            return QueryResponse(columns=["collection"], rows=rows, row_count=len(rows))
        elif op == "find":
            filt = payload.get("filter", {})
            limit = min(int(payload.get("limit", 100)), MAX_ROWS)
            cursor = client[db_name][coll_name].find(filt)
            docs = await cursor.to_list(length=limit)
            if not docs:
                return QueryResponse(columns=[], rows=[], row_count=0)
            columns = list(docs[0].keys())
            rows = [[_to_json(doc.get(c)) for c in columns] for doc in docs]
            return QueryResponse(columns=columns, rows=rows, row_count=len(docs))
        elif op == "count":
            filt = payload.get("filter", {})
            count = await client[db_name][coll_name].count_documents(filt)
            return QueryResponse(columns=["count"], rows=[[count]], row_count=1)
        else:
            return QueryResponse(columns=[], rows=[], row_count=0, error=f"Unknown op: {op!r}. Use: find, count, list_collections")
    except Exception as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))


async def _run_qdrant_query(base_url: str, api_key: Optional[str], payload_str: str) -> QueryResponse:
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        return QueryResponse(columns=[], rows=[], row_count=0,
                             error=f"Invalid JSON: {exc}. Format: {{\"op\":\"list\"}} or {{\"op\":\"info\",\"coll\":\"name\"}}")
    op = payload.get("op", "list")
    coll = payload.get("coll", "")
    if coll and not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", coll):
        return QueryResponse(columns=[], rows=[], row_count=0,
                             error=f"Invalid collection name: {coll!r}")
    headers: dict[str, str] = {}
    if api_key:
        headers["api-key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if op == "list":
                r = await client.get(f"{base_url}/collections", headers=headers)
                collections = r.json().get("result", {}).get("collections", [])
                rows = [[c["name"]] for c in collections]
                return QueryResponse(columns=["collection"], rows=rows, row_count=len(rows))
            elif op == "info":
                r = await client.get(f"{base_url}/collections/{coll}", headers=headers)
                info = r.json().get("result", {})
                rows = [[k, str(v)] for k, v in info.items()]
                return QueryResponse(columns=["key", "value"], rows=rows, row_count=len(rows))
            elif op == "scroll":
                limit = min(int(payload.get("limit", 10)), MAX_ROWS)
                r = await client.post(
                    f"{base_url}/collections/{coll}/points/scroll",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"limit": limit, "with_payload": True},
                )
                points = r.json().get("result", {}).get("points", [])
                if not points:
                    return QueryResponse(columns=[], rows=[], row_count=0)
                columns = ["id"] + list(points[0].get("payload", {}).keys())
                rows = [[p["id"]] + [_to_json(p.get("payload", {}).get(c)) for c in columns[1:]] for p in points]
                return QueryResponse(columns=columns, rows=rows, row_count=len(points))
            else:
                return QueryResponse(columns=[], rows=[], row_count=0, error=f"Unknown op: {op!r}. Use: list, info, scroll")
    except Exception as exc:
        return QueryResponse(columns=[], rows=[], row_count=0, error=str(exc))


@router.post("/{log_id}/query", response_model=QueryResponse)
async def query_database(
    log_id: int,
    payload: QueryRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    log = await session.get(CreationLog, log_id)
    if not log or log.is_deleted:
        raise HTTPException(status_code=404, detail="Database not found")

    job = await session.get(Job, log.job_id)
    if not current_user.is_admin and (job is None or job.owner != current_user.username):
        raise HTTPException(status_code=403, detail="Not authorised to query this database")

    server = await session.get(Server, log.server_id)
    if not server or not server.admin_dsn:
        raise HTTPException(status_code=400, detail="Server has no admin DSN — set it in Servers before querying")

    if server.machine_id:
        raise HTTPException(
            status_code=400,
            detail="SQL console is not supported for SSH-tunneled servers in this version",
        )

    engine = server.engine

    if not _SELECT_RE.match(payload.sql):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed in the console")

    if engine in ("postgresql", "pgvector"):
        db_dsn = server.admin_dsn.rsplit("/", 1)[0] + f"/{log.db_name}"
        return await _run_pg_query(db_dsn, payload.sql)

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
                db=log.db_name,
                autocommit=True,
            )
        except Exception:
            logger.exception("Failed to connect (mysql) for log_id=%d", log_id)
            return QueryResponse(columns=[], rows=[], row_count=0, error="Cannot connect to MySQL database")
        try:
            return await _run_mysql_query(conn, payload.sql)
        finally:
            conn.close()

    elif engine == "mongodb":
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(server.admin_dsn, serverSelectionTimeoutMS=5000)
        try:
            payload_with_db = payload.sql
            # Inject db_name so _run_mongodb_query can use it
            try:
                d = json.loads(payload.sql)
                d["db"] = log.db_name
                payload_with_db = json.dumps(d)
            except json.JSONDecodeError:
                pass
            return await _run_mongodb_query(client, payload_with_db)
        finally:
            client.close()

    elif engine == "qdrant":
        api_key = getattr(server, "api_key", None)
        return await _run_qdrant_query(server.admin_dsn, api_key, payload.sql)

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported engine for console: {engine!r}")

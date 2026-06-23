import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@router.get("/health/database")
async def health_database():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/health/queue")
async def health_queue():
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}

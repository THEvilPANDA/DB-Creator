from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect Arq Redis pool (graceful degradation if Redis is unavailable)
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        app.state.arq = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    except Exception:
        app.state.arq = None  # worker won't function, but API still serves

    yield

    if getattr(app.state, "arq", None):
        await app.state.arq.aclose()


app = FastAPI(
    title="DB Creator",
    description="Enterprise API-first PostgreSQL provisioning platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health_router)
app.include_router(api_router)

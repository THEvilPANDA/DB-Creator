from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.config import settings
from app.services.consumers import register_consumers
from app.metrics import _prometheus_available


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_consumers()

    # Connect Arq Redis pool (graceful degradation if Redis is unavailable)
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        app.state.arq = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        print(f"[ARQ] Redis pool connected: {settings.REDIS_URL}")
    except Exception as e:
        print(f"[ARQ] Failed to connect to Redis, job enqueueing disabled: {e}")
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

# Rate limiting via slowapi (graceful no-op if not installed)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    _ratelimit_available = True
except ImportError:
    _ratelimit_available = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key"],
)

app.include_router(health_router)
app.include_router(api_router)

if _prometheus_available:
    from prometheus_client import make_asgi_app
    app.mount("/metrics", make_asgi_app())

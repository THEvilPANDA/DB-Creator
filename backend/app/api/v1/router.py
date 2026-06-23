from fastapi import APIRouter

from app.api.v1.database_templates import router as database_templates_router
from app.api.v1.health import router as health_router
from app.api.v1.history import router as history_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.naming_profiles import router as naming_profiles_router
from app.api.v1.request_templates import router as request_templates_router
from app.api.v1.servers import router as servers_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(servers_router)
api_router.include_router(jobs_router)
api_router.include_router(history_router)
api_router.include_router(naming_profiles_router)
api_router.include_router(database_templates_router)
api_router.include_router(request_templates_router)

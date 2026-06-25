from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.databases import router as databases_router
from app.api.v1.database_templates import router as database_templates_router
from app.api.v1.health import router as health_router
from app.api.v1.history import router as history_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.naming_profiles import router as naming_profiles_router
from app.api.v1.request_templates import router as request_templates_router
from app.api.v1.search import router as search_router
from app.api.v1.servers import router as servers_router
from app.api.v1.machines import router as machines_router
from app.api.v1.ssh_keys import router as ssh_keys_router
from app.api.v1.stats import router as stats_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(servers_router)
api_router.include_router(jobs_router)
api_router.include_router(history_router)
api_router.include_router(databases_router)
api_router.include_router(naming_profiles_router)
api_router.include_router(database_templates_router)
api_router.include_router(request_templates_router)
api_router.include_router(admin_router)
api_router.include_router(stats_router)
api_router.include_router(search_router)
api_router.include_router(ssh_keys_router)
api_router.include_router(machines_router)

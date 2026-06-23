"""
Admin endpoints — idempotent seeders and runtime configuration.
Run once after first deployment:
  curl -X POST http://localhost:8000/api/v1/admin/seed
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import Optional

from app.config import settings
from app.database import get_session
from app.models.database_template import DatabaseTemplate
from app.models.naming_profile import NamingProfile
from app.services.approval import get_auto_approved_environments, set_auto_approved_environments

logger = logging.getLogger(__name__)

_VALID_ENVIRONMENTS = {"development", "staging", "production"}


def require_admin_key(x_admin_key: Optional[str] = Header(default=None)) -> None:
    """Guard admin endpoints with a shared secret.

    Set ADMIN_KEY in .env for production. If unset, access is logged but allowed
    (dev convenience). Phase 7 replaces this with JWT role-based auth.
    """
    if not settings.ADMIN_KEY:
        logger.warning("ADMIN_KEY not set — admin endpoint is unprotected. Set it in .env.")
        return
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(403, "Admin key required (X-Admin-Key header)")

router = APIRouter(prefix="/admin", tags=["admin"])

_DB_TEMPLATES = [
    {
        "name": "standard",
        "description": "Standard PostgreSQL — no extra extensions",
        "extensions": [],
        "permissions": {"app_user": ["CONNECT", "USAGE", "CREATE"]},
    },
    {
        "name": "ai-rag",
        "description": "AI / RAG workload — pgvector for embeddings and semantic search",
        "extensions": ["vector", "uuid-ossp"],
        "permissions": {"app_user": ["CONNECT", "USAGE", "CREATE"]},
    },
    {
        "name": "erp",
        "description": "ERP workload — hierarchical data (ltree) and pivot tables (tablefunc)",
        "extensions": ["ltree", "tablefunc", "uuid-ossp"],
        "permissions": {"app_user": ["CONNECT", "USAGE", "CREATE"]},
    },
    {
        "name": "analytics",
        "description": "Analytics workload — full-text search (pg_trgm, btree_gin, hstore)",
        "extensions": ["pg_trgm", "btree_gin", "hstore", "uuid-ossp"],
        "permissions": {"app_user": ["CONNECT", "USAGE", "CREATE"]},
    },
    {
        "name": "custom",
        "description": "Custom — no extensions, configure as needed",
        "extensions": [],
        "permissions": {},
    },
]

_NAMING_PROFILES = [
    {
        "name": "default",
        "pattern": "{environment}_{owner}_{db_name}",
        "separator": "_",
        "reserved_names": ["postgres", "template0", "template1"],
        "allow_collision": False,
        "description": "Default: {environment}_{owner}_{db_name}",
    },
    {
        "name": "team-scoped",
        "pattern": "{team}_{environment}_{db_name}",
        "separator": "_",
        "reserved_names": ["postgres", "template0", "template1"],
        "allow_collision": False,
        "description": "Team-scoped: {team}_{environment}_{db_name}",
    },
    {
        "name": "simple",
        "pattern": "{db_name}",
        "separator": "_",
        "reserved_names": ["postgres", "template0", "template1"],
        "allow_collision": True,
        "description": "Simple: uses db_name as-is (collision allowed)",
    },
]


@router.post("/seed", status_code=201)
async def seed_defaults(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_admin_key),
):
    """Idempotently seed standard database templates and naming profiles."""
    existing_tmpl = {
        r.name
        for r in (await session.execute(
            select(DatabaseTemplate.name).where(DatabaseTemplate.is_deleted == False)  # noqa: E712
        )).scalars()
    }
    existing_np = {
        r.name
        for r in (await session.execute(
            select(NamingProfile.name).where(NamingProfile.is_deleted == False)  # noqa: E712
        )).scalars()
    }

    created_templates: list[str] = []
    for spec in _DB_TEMPLATES:
        if spec["name"] not in existing_tmpl:
            session.add(DatabaseTemplate(**spec))
            created_templates.append(spec["name"])

    created_profiles: list[str] = []
    for spec in _NAMING_PROFILES:
        if spec["name"] not in existing_np:
            session.add(NamingProfile(**spec))
            created_profiles.append(spec["name"])

    await session.commit()

    return {
        "templates_created": created_templates,
        "naming_profiles_created": created_profiles,
        "skipped_templates": [s["name"] for s in _DB_TEMPLATES if s["name"] not in created_templates],
        "skipped_profiles": [s["name"] for s in _NAMING_PROFILES if s["name"] not in created_profiles],
    }


# ── Approval policy ───────────────────────────────────────────────────────────

class ApprovalPolicyUpdate(BaseModel):
    auto_approved_environments: list[str]


@router.get("/approval-policy")
async def get_approval_policy(_: None = Depends(require_admin_key)):
    """Return the environments that get auto-approved on job submission."""
    return {"auto_approved_environments": get_auto_approved_environments()}


@router.put("/approval-policy")
async def update_approval_policy(
    payload: ApprovalPolicyUpdate,
    _: None = Depends(require_admin_key),
):
    """Update which environments are auto-approved. Changes are in-process only (reset on restart)."""
    for env in payload.auto_approved_environments:
        if env.lower().strip() not in _VALID_ENVIRONMENTS:
            raise HTTPException(
                422,
                f"Unknown environment: {env!r}. Must be one of {sorted(_VALID_ENVIRONMENTS)}",
            )
    set_auto_approved_environments(payload.auto_approved_environments)
    return {"auto_approved_environments": get_auto_approved_environments()}

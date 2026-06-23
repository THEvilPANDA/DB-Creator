"""
Integration tests for naming profile preview + admin seed endpoints.
Requires live PostgreSQL — run after: docker compose up -d postgres && alembic upgrade head
"""
import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_seed_creates_standard_templates():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/admin/seed")
        assert r.status_code == 201
        body = r.json()
        assert "standard" in body["templates_created"] or "standard" in body["skipped_templates"]
        assert "ai-rag" in body["templates_created"] or "ai-rag" in body["skipped_templates"]

        # Second call is idempotent
        r2 = await client.post("/api/v1/admin/seed")
        assert r2.status_code == 201
        body2 = r2.json()
        assert body2["templates_created"] == []
        assert body2["naming_profiles_created"] == []


@pytest.mark.asyncio
async def test_naming_profile_preview():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a naming profile
        r = await client.post("/api/v1/naming-profiles", json={
            "name": "preview-test",
            "pattern": "{environment}_{owner}_{db_name}",
            "reserved_names": ["postgres"],
        })
        assert r.status_code == 201
        pid = r.json()["id"]

        # Preview it
        r2 = await client.get(
            f"/api/v1/naming-profiles/{pid}/preview",
            params={"environment": "dev", "owner": "alice", "db_name": "myapp"},
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body["resolved_name"] == "dev_alice_myapp"
        assert body["valid"] is True
        assert body["errors"] == []


@pytest.mark.asyncio
async def test_naming_profile_preview_reserved_name():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/naming-profiles", json={
            "name": "reserved-test",
            "pattern": "{db_name}",
            "reserved_names": ["postgres", "template0"],
        })
        assert r.status_code == 201
        pid = r.json()["id"]

        r2 = await client.get(
            f"/api/v1/naming-profiles/{pid}/preview",
            params={"db_name": "postgres"},
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body["valid"] is False
        assert len(body["errors"]) > 0


@pytest.mark.asyncio
async def test_job_applies_request_template():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed templates first
        await client.post("/api/v1/admin/seed")

        # Get a db template id
        tmpl_r = await client.get("/api/v1/database-templates")
        templates = [t for t in tmpl_r.json() if t["name"] == "standard"]
        assert templates, "standard template not found after seed"
        db_tmpl_id = templates[0]["id"]

        # Create request template
        rt_r = await client.post("/api/v1/request-templates", json={
            "name": "dev-standard",
            "environment": "development",
            "db_template_id": db_tmpl_id,
            "expiration_days": 30,
            "team": "platform",
        })
        assert rt_r.status_code == 201
        rt_id = rt_r.json()["id"]

        # Submit job using request template — team should be auto-filled
        job_r = await client.post("/api/v1/jobs", json={
            "owner": "alice",
            "environment": "development",
            "request_template_id": rt_id,
        })
        assert job_r.status_code == 201
        job = job_r.json()
        assert job["team"] == "platform"
        assert job["db_template_id"] == db_tmpl_id

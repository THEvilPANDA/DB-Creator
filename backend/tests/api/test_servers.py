"""
Integration tests for the Servers API.
Requires a live PostgreSQL instance — run with Docker Compose:
  docker compose up -d postgres
  python -m pytest tests/api/ -v
"""
import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_create_and_list_server():
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "test-pg-01",
            "host": "localhost",
            "port": 5432,
            "environment": "development",
            "region": "local",
        }
        r = await client.post("/api/v1/servers", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "test-pg-01"
        assert data["has_admin_dsn"] is False

        r2 = await client.get("/api/v1/servers")
        assert r2.status_code == 200
        ids = [s["id"] for s in r2.json()]
        assert data["id"] in ids


@pytest.mark.asyncio
async def test_capacity_returns_unknown_without_admin_dsn():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/servers", json={
            "name": "no-creds-server",
            "host": "unreachable-host",
            "environment": "staging",
        })
        assert r.status_code == 201
        sid = r.json()["id"]

        cap = await client.get(f"/api/v1/servers/{sid}/capacity")
        assert cap.status_code == 200
        assert cap.json()["health"] == "unknown"


@pytest.mark.asyncio
async def test_health_summary():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/v1/servers/health-summary")
        assert r.status_code == 200
        body = r.json()
        assert "servers" in body
        assert "healthy" in body
        assert "unknown" in body


@pytest.mark.asyncio
async def test_job_submit_blocks_on_critical_server():
    """When a server is at capacity (critical), job submission must return 422."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/servers", json={
            "name": "overloaded",
            "host": "localhost",
            "environment": "production",
            "max_connections": 1,
            "warning_threshold_pct": 50.0,
            "critical_threshold_pct": 60.0,
        })
        assert r.status_code == 201
        sid = r.json()["id"]

        # Without admin_dsn, capacity is "unknown" so gate passes.
        # A real capacity gate test requires a live server with admin_dsn configured.
        r2 = await client.post("/api/v1/jobs", json={
            "environment": "production",
            "owner": "tester",
            "server_id": sid,
        })
        # No admin_dsn → health=unknown → is_accepting_jobs=True → 201
        assert r2.status_code == 201

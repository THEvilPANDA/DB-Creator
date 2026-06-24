import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.provisioner.qdrant import QdrantProvisioner
from app.services.provisioner.base import DatabaseSpec, UserSpec, PermissionSpec


def _provisioner(api_key=None):
    return QdrantProvisioner(
        base_url="http://localhost:6333",
        api_key=api_key,
        server_id=3,
        warning_threshold_pct=75.0,
        critical_threshold_pct=90.0,
    )


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status_code
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.asyncio
async def test_qdrant_database_exists_true():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = _mock_response(200, {"result": {"name": "mycol"}})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        result = await p.database_exists("mycol")
    assert result is True


@pytest.mark.asyncio
async def test_qdrant_database_exists_false():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = _mock_response(404, {"status": {"error": "Not found"}})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        result = await p.database_exists("notexist")
    assert result is False


@pytest.mark.asyncio
async def test_qdrant_create_database_success():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    # database_exists returns False → proceed with PUT
    mock_client.get.return_value = _mock_response(404, {})
    mock_client.put.return_value = _mock_response(200, {"result": True})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        spec = DatabaseSpec(name="mycol", owner="alice", options={"size": 1536, "distance": "Cosine"})
        result = await p.create_database(spec)
    assert result.success is True


@pytest.mark.asyncio
async def test_qdrant_create_user_noop():
    p = _provisioner()
    result = await p.create_user(UserSpec(username="alice", password="pw", db_name="mycol"))
    assert result.success is True


@pytest.mark.asyncio
async def test_qdrant_grant_permissions_noop():
    p = _provisioner()
    await p.grant_permissions(PermissionSpec(db_name="mycol", username="alice"))


@pytest.mark.asyncio
async def test_qdrant_enable_extensions_noop():
    p = _provisioner()
    await p.enable_extensions("mycol", [])


@pytest.mark.asyncio
async def test_qdrant_get_capacity():
    p = _provisioner()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = _mock_response(200, {"result": {"collections": [{"name": "a"}, {"name": "b"}]}})
    with patch("app.services.provisioner.qdrant.httpx.AsyncClient", return_value=mock_client):
        m = await p.get_capacity()
    assert m.server_id == 3
    assert m.db_count == 2


@pytest.mark.asyncio
async def test_qdrant_api_key_included_in_headers():
    p = _provisioner(api_key="my-secret-key")
    headers = p._headers()
    assert headers.get("api-key") == "my-secret-key"


def test_qdrant_no_api_key_no_header():
    p = _provisioner(api_key=None)
    assert "api-key" not in p._headers()

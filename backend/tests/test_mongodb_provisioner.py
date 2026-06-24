import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.services.provisioner.mongodb import MongoDBProvisioner
from app.services.provisioner.base import DatabaseSpec, UserSpec, PermissionSpec


def _provisioner():
    return MongoDBProvisioner(
        dsn="mongodb://admin:secret@localhost:27017/",
        server_id=2,
        warning_threshold_pct=75.0,
        critical_threshold_pct=90.0,
    )


@pytest.mark.asyncio
async def test_mongodb_database_exists_true():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=["mydb", "admin"])
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.database_exists("mydb")
    assert result is True


@pytest.mark.asyncio
async def test_mongodb_database_exists_false():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=["admin", "local"])
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.database_exists("notexist")
    assert result is False


@pytest.mark.asyncio
async def test_mongodb_create_database_success():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=[])
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
    mock_col.delete_many = AsyncMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.create_database(DatabaseSpec(name="newdb", owner="alice"))
    assert result.success is True


@pytest.mark.asyncio
async def test_mongodb_create_user_success():
    p = _provisioner()
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1.0})
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        result = await p.create_user(UserSpec(username="alice", password="pw", db_name="mydb"))
    assert result.success is True


@pytest.mark.asyncio
async def test_mongodb_grant_permissions_noop():
    p = _provisioner()
    # grant_permissions is a no-op for MongoDB (roles assigned at create_user time)
    await p.grant_permissions(PermissionSpec(db_name="mydb", username="alice"))


@pytest.mark.asyncio
async def test_mongodb_enable_extensions_noop():
    p = _provisioner()
    await p.enable_extensions("mydb", ["ext"])


@pytest.mark.asyncio
async def test_mongodb_get_capacity():
    p = _provisioner()
    mock_client = MagicMock()
    mock_client.list_database_names = AsyncMock(return_value=["mydb", "admin", "local"])
    mock_admin_db = MagicMock()
    mock_admin_db.command = AsyncMock(return_value={
        "connections": {"current": 3},
        "ok": 1.0,
    })
    mock_client.__getitem__ = MagicMock(return_value=mock_admin_db)
    with patch("app.services.provisioner.mongodb.AsyncIOMotorClient", return_value=mock_client):
        m = await p.get_capacity()
    assert m.server_id == 2
    assert isinstance(m.active_connections, int)

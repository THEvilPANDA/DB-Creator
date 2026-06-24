import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_server(engine="postgresql"):
    s = MagicMock()
    s.id = 1
    s.engine = engine
    s.admin_dsn = "postgresql://u:p@h/db"
    s.api_key = None
    s.host = "localhost"
    s.port = 5432
    s.warning_threshold_pct = 75.0
    s.critical_threshold_pct = 90.0
    return s


def _make_job(engine="postgresql"):
    j = MagicMock()
    j.id = 10
    j.status = "queued"
    j.server_id = 1
    j.db_name = "testdb"
    j.environment = "development"
    j.db_template_id = None
    j.owner = "alice"
    return j


@pytest.mark.asyncio
async def test_provision_uses_factory():
    """Verify provision_database calls get_provisioner, not PostgreSQLProvisioner directly."""
    from app.workers.tasks import provision_database

    mock_provisioner = AsyncMock()
    mock_provisioner.create_user.return_value = MagicMock(success=True)
    mock_provisioner.create_database.return_value = MagicMock(success=True, db_name="testdb")
    mock_provisioner.grant_permissions = AsyncMock()
    mock_provisioner.enable_extensions = AsyncMock()

    mock_session = AsyncMock()
    mock_session.get.side_effect = lambda model, pk: {
        (None, 10): _make_job(),
        (None, 1): _make_server(),
    }.get((model, pk), _make_job() if pk == 10 else _make_server())

    def _get_side_effect(model, pk):
        from app.models.job import Job
        from app.models.server import Server
        if model is Job:
            return _make_job()
        if model is Server:
            return _make_server()
        return None

    mock_session.get = AsyncMock(side_effect=_get_side_effect)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("app.workers.tasks.AsyncSessionLocal") as mock_session_factory, \
         patch("app.workers.tasks.get_provisioner", return_value=mock_provisioner) as mock_factory:
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await provision_database({}, job_id=10)

    mock_factory.assert_called_once()


@pytest.mark.asyncio
async def test_mysql_connection_uri_format():
    """Verify connection_uri uses correct scheme for MySQL."""
    from app.workers.tasks import _build_connection_uri
    uri = _build_connection_uri(
        engine="mysql", user="alice", password="pw", host="db", port=3306, db_name="mydb"
    )
    assert uri.startswith("mysql://")
    assert "mydb" in uri


@pytest.mark.asyncio
async def test_mongodb_connection_uri_format():
    from app.workers.tasks import _build_connection_uri
    uri = _build_connection_uri(
        engine="mongodb", user="alice", password="pw", host="db", port=27017, db_name="mydb"
    )
    assert uri.startswith("mongodb://")


@pytest.mark.asyncio
async def test_qdrant_connection_uri_format():
    from app.workers.tasks import _build_connection_uri
    uri = _build_connection_uri(
        engine="qdrant", user="", password="", host="db", port=6333, db_name="mycol"
    )
    assert "mycol" in uri

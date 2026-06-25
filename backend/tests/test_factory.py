import pytest
from unittest.mock import MagicMock


def _server(engine, admin_dsn="postgresql://u:p@h/db", api_key=None):
    s = MagicMock()
    s.engine = engine
    s.admin_dsn = admin_dsn
    s.api_key = api_key
    s.id = 1
    s.warning_threshold_pct = 75.0
    s.critical_threshold_pct = 90.0
    s.host = "localhost"
    s.port = 5432
    s.machine_id = None
    return s


@pytest.mark.asyncio
async def test_factory_postgresql():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.postgresql import PostgreSQLProvisioner
    async with get_provisioner(_server("postgresql")) as p:
        assert isinstance(p, PostgreSQLProvisioner)


@pytest.mark.asyncio
async def test_factory_pgvector():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.pgvector import PgvectorProvisioner
    async with get_provisioner(_server("pgvector")) as p:
        assert isinstance(p, PgvectorProvisioner)


@pytest.mark.asyncio
async def test_factory_mysql():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.mysql import MySQLProvisioner
    async with get_provisioner(_server("mysql", admin_dsn="mysql://u:p@h/")) as p:
        assert isinstance(p, MySQLProvisioner)


@pytest.mark.asyncio
async def test_factory_mongodb():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.mongodb import MongoDBProvisioner
    async with get_provisioner(_server("mongodb", admin_dsn="mongodb://u:p@h/")) as p:
        assert isinstance(p, MongoDBProvisioner)


@pytest.mark.asyncio
async def test_factory_qdrant():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.qdrant import QdrantProvisioner
    async with get_provisioner(_server("qdrant", admin_dsn="http://localhost:6333")) as p:
        assert isinstance(p, QdrantProvisioner)


@pytest.mark.asyncio
async def test_factory_unknown_raises():
    from app.services.provisioner.factory import get_provisioner
    with pytest.raises(ValueError, match="Unknown engine"):
        async with get_provisioner(_server("oracle")):
            pass


def test_database_spec_options_default():
    from app.services.provisioner.base import DatabaseSpec
    spec = DatabaseSpec(name="mydb", owner="alice")
    assert spec.options == {}


def test_database_spec_options_custom():
    from app.services.provisioner.base import DatabaseSpec
    spec = DatabaseSpec(name="mydb", owner="alice", options={"dimensions": 1536})
    assert spec.options == {"dimensions": 1536}


@pytest.mark.asyncio
async def test_get_provisioner_direct_no_machine_id():
    from app.services.provisioner.factory import get_provisioner
    from unittest.mock import MagicMock
    server = MagicMock()
    server.machine_id = None
    server.engine = "postgresql"
    server.admin_dsn = "postgresql://u:p@localhost:5432/db"
    server.id = 1
    server.warning_threshold_pct = 75.0
    server.critical_threshold_pct = 90.0
    async with get_provisioner(server) as provisioner:
        assert provisioner is not None

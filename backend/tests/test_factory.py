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
    return s


def test_factory_postgresql():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.postgresql import PostgreSQLProvisioner
    p = get_provisioner(_server("postgresql"))
    assert isinstance(p, PostgreSQLProvisioner)


def test_factory_pgvector():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.pgvector import PgvectorProvisioner
    p = get_provisioner(_server("pgvector"))
    assert isinstance(p, PgvectorProvisioner)


def test_factory_mysql():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.mysql import MySQLProvisioner
    p = get_provisioner(_server("mysql", admin_dsn="mysql://u:p@h/"))
    assert isinstance(p, MySQLProvisioner)


def test_factory_mongodb():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.mongodb import MongoDBProvisioner
    p = get_provisioner(_server("mongodb", admin_dsn="mongodb://u:p@h/"))
    assert isinstance(p, MongoDBProvisioner)


def test_factory_qdrant():
    from app.services.provisioner.factory import get_provisioner
    from app.services.provisioner.qdrant import QdrantProvisioner
    p = get_provisioner(_server("qdrant", admin_dsn="http://localhost:6333"))
    assert isinstance(p, QdrantProvisioner)


def test_factory_unknown_raises():
    from app.services.provisioner.factory import get_provisioner
    with pytest.raises(ValueError, match="Unknown engine"):
        get_provisioner(_server("oracle"))


def test_database_spec_options_default():
    from app.services.provisioner.base import DatabaseSpec
    spec = DatabaseSpec(name="mydb", owner="alice")
    assert spec.options == {}


def test_database_spec_options_custom():
    from app.services.provisioner.base import DatabaseSpec
    spec = DatabaseSpec(name="mydb", owner="alice", options={"dimensions": 1536})
    assert spec.options == {"dimensions": 1536}

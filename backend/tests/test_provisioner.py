import inspect

from app.services.provisioner.base import (
    CapacityMetrics,
    DatabaseProvisioner,
    DatabaseSpec,
    UserSpec,
)
from app.services.provisioner.postgresql import PostgreSQLProvisioner


def test_provisioner_implements_all_abstract_methods():
    abstract_methods = {
        name
        for name, method in inspect.getmembers(DatabaseProvisioner)
        if getattr(method, "__isabstractmethod__", False)
    }
    implemented = set(dir(PostgreSQLProvisioner))
    assert abstract_methods.issubset(implemented)


def test_database_spec_defaults():
    spec = DatabaseSpec(name="mydb", owner="alice")
    assert spec.name == "mydb"
    assert spec.owner == "alice"
    assert spec.extensions == []
    assert spec.template is None


def test_user_spec_fields():
    spec = UserSpec(username="alice", password="secret", db_name="mydb")
    assert spec.username == "alice"


def test_capacity_metrics_zero_disk():
    m = CapacityMetrics(1, 0, 0, 0.0, 0.0, 75.0, 90.0)
    assert m.health == "healthy"


from app.services.provisioner.pgvector import PgvectorProvisioner


def test_pgvector_is_subclass_of_postgresql():
    assert issubclass(PgvectorProvisioner, PostgreSQLProvisioner)


def test_pgvector_implements_all_abstract_methods():
    abstract_methods = {
        name for name, method in inspect.getmembers(DatabaseProvisioner)
        if getattr(method, "__isabstractmethod__", False)
    }
    assert abstract_methods.issubset(set(dir(PgvectorProvisioner)))


def test_pgvector_is_not_postgresql():
    p = PgvectorProvisioner(dsn="postgresql://u:p@h/db", server_id=1)
    assert type(p) is PgvectorProvisioner

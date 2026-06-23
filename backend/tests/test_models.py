from app.models import ApprovalRequest, AuditLog, CreationLog, DatabaseTemplate, Job, NamingProfile, RequestTemplate, Server


def test_server_defaults():
    s = Server(name="pg-dev-01", host="localhost", environment="development")
    assert s.is_deleted is False
    assert s.is_active is True
    assert s.port == 5432
    assert s.engine == "postgresql"
    assert s.max_connections == 100


def test_naming_profile_defaults():
    np = NamingProfile(name="standard", pattern="{env}_{team}_{purpose}")
    assert np.is_deleted is False
    assert np.allow_collision is False
    assert np.separator == "_"


def test_database_template_defaults():
    dt = DatabaseTemplate(name="standard")
    assert dt.is_deleted is False
    assert dt.extensions == []
    assert dt.permissions == {}


def test_request_template_defaults():
    rt = RequestTemplate(name="ai-sandbox", environment="development")
    assert rt.is_deleted is False
    assert rt.expiration_days == 90


def test_job_default_status():
    j = Job(db_name="mydb", environment="development", owner="alice")
    assert j.status == "pending"
    assert j.is_deleted is False


def test_approval_request_fields():
    ar = ApprovalRequest(job_id=1, status="pending")
    assert ar.approver is None
    assert ar.decided_at is None


def test_creation_log_defaults():
    cl = CreationLog(job_id=1, server_id=1, db_name="mydb")
    assert cl.connection_uri is None
    assert cl.is_deleted is False


def test_audit_log_has_no_soft_delete():
    al = AuditLog(actor="system", action="create", entity_type="Server", entity_id=1)
    assert not hasattr(al, "is_deleted")

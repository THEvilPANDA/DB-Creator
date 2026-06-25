import pytest
from unittest.mock import MagicMock, patch
from cryptography.fernet import Fernet

from app.dependencies import get_current_user
from app.main import app


FERNET_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def patch_fernet(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", FERNET_KEY)
    with patch("app.services.encryption.settings") as m:
        m.FERNET_KEY = FERNET_KEY
        yield m


@pytest.mark.asyncio
async def test_console_blocked_for_ssh_tunneled_server(client, db_session):
    from app.models.server import Server
    from app.models.creation_log import CreationLog
    from app.models.job import Job
    from app.models.machine import Machine
    from app.models.ssh_key import SSHKey
    from app.services.encryption import encrypt

    # SSH key (encrypted_private_key is a dummy — we never SSH-connect in this test)
    ssh_key = SSHKey(name="guard-test-key", username="ubuntu", encrypted_private_key=encrypt("DUMMY"))
    db_session.add(ssh_key)
    await db_session.commit()
    await db_session.refresh(ssh_key)

    # Machine — needed to satisfy FK on server.machine_id
    machine = Machine(ip="10.99.0.1", ssh_port=22, ssh_key_id=ssh_key.id)
    db_session.add(machine)
    await db_session.commit()
    await db_session.refresh(machine)

    # Server with machine_id set and admin_dsn present (admin_dsn needed to pass the
    # existing "no admin DSN" guard that comes before our new SSH guard)
    server = Server(
        name="guard-test-server", host="10.99.0.1", port=5432,
        engine="postgresql", environment="development",
        machine_id=machine.id,
        admin_dsn="postgresql://user:pass@10.99.0.1/db",
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)

    job = Job(
        db_name="testdb", environment="development",
        status="succeeded", owner="testuser", server_id=server.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    log = CreationLog(
        job_id=job.id, server_id=server.id,
        db_name="testdb",
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    mock_admin = MagicMock(is_admin=True, username="testuser", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    try:
        r = await client.post(
            f"/api/v1/databases/{log.id}/query",
            json={"sql": "SELECT 1"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    assert "SSH-tunneled" in r.json()["detail"]

    # Close the session explicitly so the function-scoped fixture teardown
    # does not try to ROLLBACK on a closed event loop.
    await db_session.close()

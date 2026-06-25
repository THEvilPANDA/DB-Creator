import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

FERNET_KEY = Fernet.generate_key().decode()


def _make_pem():
    pk = rsa.generate_private_key(65537, 2048, default_backend())
    return pk.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture(autouse=True)
async def override_require_admin(client):
    from app.dependencies import require_admin
    from app.main import app
    from unittest.mock import MagicMock
    app.dependency_overrides[require_admin] = lambda: MagicMock(is_admin=True, id=1, is_active=True)
    yield


@pytest.fixture(autouse=True)
def patch_fernet(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", FERNET_KEY)
    with patch("app.services.encryption.settings") as m:
        m.FERNET_KEY = FERNET_KEY
        yield m


@pytest.fixture
async def ssh_key_id(client):
    r = await client.post("/api/v1/ssh-keys", json={
        "name": "test-key", "username": "ubuntu", "private_key": _make_pem()
    })
    return r.json()["id"]


@pytest.mark.asyncio
async def test_create_and_list_machine(client, ssh_key_id):
    r = await client.post("/api/v1/machines", json={
        "ip": "192.168.1.10", "ssh_port": 22, "ssh_key_id": ssh_key_id, "label": "dev-box"
    })
    assert r.status_code == 201
    data = r.json()
    assert data["ip"] == "192.168.1.10"
    assert data["status"] == "unknown"
    r2 = await client.get("/api/v1/machines")
    assert any(m["ip"] == "192.168.1.10" for m in r2.json())


@pytest.mark.asyncio
async def test_delete_machine(client, ssh_key_id):
    r = await client.post("/api/v1/machines", json={
        "ip": "192.168.1.20", "ssh_port": 22, "ssh_key_id": ssh_key_id
    })
    machine_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/machines/{machine_id}")
    assert r2.status_code == 200
    r3 = await client.get("/api/v1/machines")
    assert not any(m["id"] == machine_id for m in r3.json())


@pytest.mark.asyncio
async def test_check_machine_online(client, ssh_key_id):
    r = await client.post("/api/v1/machines", json={
        "ip": "192.168.1.30", "ssh_port": 22, "ssh_key_id": ssh_key_id
    })
    machine_id = r.json()["id"]
    mock_conn = MagicMock()
    mock_conn.get_server_host_key.return_value = None
    mock_conn.run = AsyncMock(side_effect=[
        MagicMock(stdout="myhost\n"),
        MagicMock(stdout="Linux myhost 5.15 #1 SMP\n"),
    ])
    with patch("app.services.ssh_tunnel.asyncssh.connect", new=AsyncMock(return_value=mock_conn)), \
         patch("app.services.ssh_tunnel.asyncssh.import_private_key", return_value=MagicMock()):
        r2 = await client.post(f"/api/v1/machines/{machine_id}/check")
    assert r2.status_code == 200
    assert r2.json()["status"] == "online"
    assert r2.json()["hostname"] == "myhost"


@pytest.mark.asyncio
async def test_scan_rejects_public_cidr(client):
    r = await client.post("/api/v1/machines/scan", json={"cidr": "8.8.8.0/24", "method": "port22"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_scan_private_cidr(client):
    with patch("app.api.v1.machines.scan", new=AsyncMock(return_value=[
        {"ip": "192.168.1.1", "ping_ok": False, "ssh_open": True},
    ])):
        r = await client.post("/api/v1/machines/scan", json={"cidr": "192.168.1.0/30", "method": "port22"})
    assert r.status_code == 200
    assert r.json()[0]["ip"] == "192.168.1.1"


@pytest.mark.asyncio
async def test_detect_engines_via_ssh(client, ssh_key_id):
    r = await client.post("/api/v1/machines", json={
        "ip": "192.168.3.10", "ssh_port": 22, "ssh_key_id": ssh_key_id
    })
    assert r.status_code == 201
    machine_id = r.json()["id"]

    mock_conn = MagicMock()

    async def _mock_run(cmd, check=False):
        m = MagicMock()
        m.stdout = "open\n" if "5432" in cmd else "closed\n"
        return m

    mock_conn.run = AsyncMock(side_effect=_mock_run)

    with patch("app.services.ssh_tunnel.asyncssh.connect", new=AsyncMock(return_value=mock_conn)), \
         patch("app.services.ssh_tunnel.asyncssh.import_private_key", return_value=MagicMock()):
        r2 = await client.post(f"/api/v1/machines/{machine_id}/detect-engines")

    assert r2.status_code == 200
    results = {item["engine"]: item["open"] for item in r2.json()}
    assert results["postgresql"] is True
    assert results["mysql"] is False
    assert results["mongodb"] is False

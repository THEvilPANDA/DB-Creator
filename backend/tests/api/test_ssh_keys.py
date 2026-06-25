import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet

FERNET_KEY = Fernet.generate_key().decode()


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

@pytest.mark.asyncio
async def test_create_and_list_ssh_key(client):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    r = await client.post("/api/v1/ssh-keys", json={
        "name": "my-key", "username": "ubuntu", "private_key": pem
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "my-key"
    assert "private_key" not in data
    assert "encrypted_private_key" not in data
    r2 = await client.get("/api/v1/ssh-keys")
    assert r2.status_code == 200
    assert any(k["name"] == "my-key" for k in r2.json())

@pytest.mark.asyncio
async def test_delete_ssh_key(client):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    r = await client.post("/api/v1/ssh-keys", json={
        "name": "delete-me", "username": "root", "private_key": pem
    })
    key_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/ssh-keys/{key_id}")
    assert r2.status_code == 200
    r3 = await client.get("/api/v1/ssh-keys")
    assert not any(k["id"] == key_id for k in r3.json())

@pytest.mark.asyncio
async def test_create_with_invalid_key_returns_422(client):
    r = await client.post("/api/v1/ssh-keys", json={
        "name": "bad", "username": "ubuntu", "private_key": "not-a-pem"
    })
    assert r.status_code == 422

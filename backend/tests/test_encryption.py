import pytest
from unittest.mock import patch
from app.services.encryption import encrypt, decrypt


def test_roundtrip():
    key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    with patch("app.services.encryption.settings") as mock_settings:
        # Generate a valid Fernet key for tests
        from cryptography.fernet import Fernet
        real_key = Fernet.generate_key().decode()
        mock_settings.FERNET_KEY = real_key
        ciphertext = encrypt("hello secret")
        assert decrypt(ciphertext) == "hello secret"


def test_no_key_raises():
    with patch("app.services.encryption.settings") as mock_settings:
        mock_settings.FERNET_KEY = ""
        with pytest.raises(RuntimeError, match="FERNET_KEY"):
            encrypt("anything")

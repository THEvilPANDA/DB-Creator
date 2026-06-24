import pytest
import jwt

from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.config import settings


def test_hash_and_verify_roundtrip():
    pw = "s3cr3tPassword!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)


def test_wrong_password_fails():
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_access_token_payload():
    token = create_access_token(user_id=42, username="alice", is_admin=False)
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["username"] == "alice"
    assert payload["is_admin"] is False
    assert payload["type"] == "access"


def test_admin_flag_in_access_token():
    token = create_access_token(user_id=1, username="root", is_admin=True)
    payload = decode_token(token)
    assert payload["is_admin"] is True


def test_refresh_token_type():
    token = create_refresh_token(user_id=7)
    payload = decode_token(token)
    assert payload["sub"] == "7"
    assert payload["type"] == "refresh"


def test_access_and_refresh_tokens_differ():
    access = create_access_token(user_id=1, username="u", is_admin=False)
    refresh = create_refresh_token(user_id=1)
    assert access != refresh


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("not.a.token")


def test_decode_wrong_secret_raises():
    token = jwt.encode({"sub": "1", "type": "access"}, "other-secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)

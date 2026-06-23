"""Unit tests for admin endpoint key guard."""
import pytest
from fastapi import HTTPException

from app.api.v1.admin import require_admin_key


def test_no_key_configured_allows_any(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_KEY", "")
    # Should not raise regardless of header value
    require_admin_key(x_admin_key=None)
    require_admin_key(x_admin_key="anything")


def test_key_configured_accepts_correct(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_KEY", "supersecret")
    require_admin_key(x_admin_key="supersecret")


def test_key_configured_rejects_missing(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_KEY", "supersecret")
    with pytest.raises(HTTPException) as exc:
        require_admin_key(x_admin_key=None)
    assert exc.value.status_code == 403


def test_key_configured_rejects_wrong(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_KEY", "supersecret")
    with pytest.raises(HTTPException) as exc:
        require_admin_key(x_admin_key="wrongkey")
    assert exc.value.status_code == 403


def test_key_not_leaked_in_error_detail(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_KEY", "supersecret")
    with pytest.raises(HTTPException) as exc:
        require_admin_key(x_admin_key="wrong")
    assert "supersecret" not in str(exc.value.detail)

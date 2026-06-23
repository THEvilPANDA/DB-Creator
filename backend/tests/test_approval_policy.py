"""Unit tests for mutable approval policy."""
import pytest
from app.services.approval import (
    ApprovalService,
    get_auto_approved_environments,
    set_auto_approved_environments,
)


@pytest.fixture(autouse=True)
def _restore_policy():
    original = get_auto_approved_environments()
    yield
    set_auto_approved_environments(original)


def test_initial_state():
    envs = get_auto_approved_environments()
    assert "development" in envs
    assert "staging" in envs
    assert "production" not in envs


def test_set_replaces_fully():
    set_auto_approved_environments(["production"])
    assert get_auto_approved_environments() == ["production"]


def test_set_empty_clears():
    set_auto_approved_environments([])
    assert get_auto_approved_environments() == []


def test_is_auto_approved_respects_update():
    svc = ApprovalService()
    set_auto_approved_environments(["production"])
    assert svc.is_auto_approved("production")
    assert not svc.is_auto_approved("development")
    assert not svc.is_auto_approved("staging")


def test_case_insensitive():
    svc = ApprovalService()
    set_auto_approved_environments(["Development"])
    assert svc.is_auto_approved("development")
    assert svc.is_auto_approved("DEVELOPMENT")


def test_whitespace_stripped():
    set_auto_approved_environments(["  staging  "])
    envs = get_auto_approved_environments()
    assert "staging" in envs
    assert "  staging  " not in envs

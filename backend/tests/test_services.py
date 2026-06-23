import pytest

from app.services.approval import ApprovalService
from app.services.events import DomainEvent, EventPublisher
from app.services.naming import NamingService
from app.services.provisioner.base import CapacityMetrics


def test_approval_dev_auto_approved():
    svc = ApprovalService()
    assert svc.is_auto_approved("development") is True


def test_approval_staging_auto_approved():
    svc = ApprovalService()
    assert svc.is_auto_approved("staging") is True


def test_approval_prod_not_auto_approved():
    svc = ApprovalService()
    assert svc.is_auto_approved("production") is False


def test_naming_resolve_pattern():
    svc = NamingService()
    result = svc.resolve(pattern="{env}_{team}_{purpose}", env="dev", team="ai", purpose="rag")
    assert result == "dev_ai_rag"


def test_naming_reserved_name_raises():
    svc = NamingService()
    with pytest.raises(ValueError, match="reserved"):
        svc.validate_name("postgres", reserved=["postgres", "template0"])


def test_naming_invalid_name_raises():
    svc = NamingService()
    with pytest.raises(ValueError):
        svc.validate_name("123bad", reserved=[])


def test_event_publisher_collects_events():
    pub = EventPublisher()
    pub.publish(DomainEvent(name="DatabaseRequested", payload={"job_id": 1}))
    assert len(pub.events) == 1
    assert pub.events[0].name == "DatabaseRequested"


def test_event_publisher_fires_handler():
    pub = EventPublisher()
    received = []
    pub.subscribe("TestEvent", lambda e: received.append(e.payload))
    pub.publish(DomainEvent("TestEvent", {"x": 42}))
    assert received == [{"x": 42}]


def test_capacity_metrics_healthy():
    m = CapacityMetrics(1, 10, 5, 10.0, 90.0, 75.0, 90.0)
    assert m.health == "healthy"


def test_capacity_metrics_warning():
    m = CapacityMetrics(1, 10, 5, 80.0, 20.0, 75.0, 90.0)
    assert m.health == "warning"


def test_capacity_metrics_critical():
    m = CapacityMetrics(1, 10, 5, 92.0, 8.0, 75.0, 90.0)
    assert m.health == "critical"

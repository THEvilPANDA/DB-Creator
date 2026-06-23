"""Unit tests for domain event consumers."""
from app.services.consumers import register_consumers
from app.services.events import DomainEvent, EventPublisher


def _fresh_publisher():
    return EventPublisher()


def test_register_consumers_wires_four_events(monkeypatch):
    pub = _fresh_publisher()
    monkeypatch.setattr("app.services.consumers.publisher", pub)
    register_consumers()
    assert "DatabaseRequested" in pub._handlers
    assert "DatabaseProvisioningStarted" in pub._handlers
    assert "DatabaseProvisioningCompleted" in pub._handlers
    assert "DatabaseProvisioningFailed" in pub._handlers


def test_consumers_fire_on_publish(monkeypatch):
    pub = _fresh_publisher()
    monkeypatch.setattr("app.services.consumers.publisher", pub)
    register_consumers()

    fired = []
    pub.subscribe("DatabaseRequested", lambda e: fired.append(e.payload))

    pub.publish(DomainEvent("DatabaseRequested", {"job_id": 1, "environment": "dev"}))
    assert len(fired) == 1
    assert fired[0]["job_id"] == 1


def test_provisioning_completed_consumer_fires(monkeypatch):
    pub = _fresh_publisher()
    monkeypatch.setattr("app.services.consumers.publisher", pub)
    register_consumers()

    received = []
    pub.subscribe("DatabaseProvisioningCompleted", lambda e: received.append(e))

    pub.publish(DomainEvent("DatabaseProvisioningCompleted", {"job_id": 5, "db_name": "mydb", "db_user": "mydb_user"}))
    assert len(received) == 1
    assert received[0].payload["db_name"] == "mydb"


def test_provisioning_failed_consumer_fires(monkeypatch, caplog):
    import logging
    pub = _fresh_publisher()
    monkeypatch.setattr("app.services.consumers.publisher", pub)
    register_consumers()

    with caplog.at_level(logging.WARNING, logger="app.services.consumers"):
        pub.publish(DomainEvent("DatabaseProvisioningFailed", {"job_id": 7, "error": "timeout"}))

    assert any("DatabaseProvisioningFailed" in r.message for r in caplog.records)

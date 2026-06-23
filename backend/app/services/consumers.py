"""Domain event consumers — log-based placeholders.

Phase 5/backlog: swap logger calls for real Slack webhook, Teams webhook,
or SIEM connector by replacing the handler bodies and re-registering.
"""
import logging

from app.services.events import DomainEvent, publisher

logger = logging.getLogger(__name__)


def _on_database_requested(event: DomainEvent) -> None:
    logger.info(
        "[EVENT] DatabaseRequested job_id=%s environment=%s",
        event.payload.get("job_id"),
        event.payload.get("environment"),
    )


def _on_provisioning_started(event: DomainEvent) -> None:
    logger.info(
        "[EVENT] DatabaseProvisioningStarted job_id=%s",
        event.payload.get("job_id"),
    )


def _on_provisioning_completed(event: DomainEvent) -> None:
    logger.info(
        "[EVENT] DatabaseProvisioningCompleted job_id=%s db=%s user=%s",
        event.payload.get("job_id"),
        event.payload.get("db_name"),
        event.payload.get("db_user"),
    )


def _on_provisioning_failed(event: DomainEvent) -> None:
    logger.warning(
        "[EVENT] DatabaseProvisioningFailed job_id=%s error=%s",
        event.payload.get("job_id"),
        event.payload.get("error"),
    )


def register_consumers() -> None:
    publisher.subscribe("DatabaseRequested", _on_database_requested)
    publisher.subscribe("DatabaseProvisioningStarted", _on_provisioning_started)
    publisher.subscribe("DatabaseProvisioningCompleted", _on_provisioning_completed)
    publisher.subscribe("DatabaseProvisioningFailed", _on_provisioning_failed)

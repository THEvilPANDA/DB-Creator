from typing import Any

from app.models.audit_log import AuditLog


async def write_audit(
    session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    ))

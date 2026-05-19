import uuid
from datetime import date, datetime
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system import AuditLog


def _serialize(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value


async def log_audit_event(
    session: AsyncSession,
    user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    details: dict = None
):
    audit = AuditLog(
        actor_id=user_id,
        action=action,
        target_kind=entity_type,
        target_id=str(entity_id),
        payload=_serialize(details) if details else {}
    )
    session.add(audit)

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system import AuditLog

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
        payload=details or {}
    )
    session.add(audit)

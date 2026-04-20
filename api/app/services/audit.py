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
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {}
    )
    session.add(audit)

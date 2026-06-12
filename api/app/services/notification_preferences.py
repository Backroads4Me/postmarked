import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationFrequency
from app.models.user import NotificationPreference


async def get_or_create_notification_preference(
    session: AsyncSession, user_id: uuid.UUID
) -> NotificationPreference:
    preference, _created = await get_or_create_notification_preference_with_status(session, user_id)
    return preference


async def get_or_create_notification_preference_with_status(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[NotificationPreference, bool]:
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    preference = result.scalars().first()
    if preference:
        return preference, False

    preference = NotificationPreference(
        user_id=user_id,
        frequency=NotificationFrequency.ALL_UPDATES,
    )
    session.add(preference)
    await session.flush()
    return preference, True

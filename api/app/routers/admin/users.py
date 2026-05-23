import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.enums import ApprovalState, NotificationFrequency, UserRole
from app.models.user import NotificationPreference, User
from app.schemas.user import PUBLIC_NOTIFICATION_FREQUENCIES

router = APIRouter(prefix="/users", tags=["admin-users"])


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    approval_state: ApprovalState
    is_active: bool
    role: str
    notification_frequency: NotificationFrequency


class NotificationPreferenceUpdate(BaseModel):
    notification_frequency: NotificationFrequency


async def _get_or_create_preference(session: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    preference = result.scalars().first()
    if preference:
        return preference

    preference = NotificationPreference(user_id=user_id, frequency=NotificationFrequency.NONE)
    session.add(preference)
    await session.flush()
    return preference


async def _summary(session: AsyncSession, user: User) -> UserSummary:
    preference = await _get_or_create_preference(session, user.id)
    return UserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        approval_state=user.approval_state,
        is_active=user.is_active,
        role=user.role.value,
        notification_frequency=preference.frequency,
    )


@router.get("", response_model=List[UserSummary])
async def list_users(
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    query = select(User)
    if status == "pending":
        query = query.where(User.approval_state == ApprovalState.PENDING)
    elif status == "approved":
        query = query.where(User.approval_state == ApprovalState.APPROVED)
    rows = (await session.execute(query.order_by(User.created_at.asc()))).scalars().all()
    summaries = [await _summary(session, u) for u in rows]
    await session.commit()
    return summaries


@router.post("/{user_id}/approve", response_model=UserSummary)
async def approve_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.approval_state = ApprovalState.APPROVED
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    summary = await _summary(session, user)
    await session.commit()
    return summary


@router.post("/{user_id}/reject", response_model=UserSummary)
async def reject_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.approval_state = ApprovalState.REJECTED
    user.is_active = False
    await session.commit()
    await session.refresh(user)
    summary = await _summary(session, user)
    await session.commit()
    return summary


@router.patch("/{user_id}/notifications", response_model=UserSummary)
async def update_user_notifications(
    user_id: uuid.UUID,
    payload: NotificationPreferenceUpdate,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    if payload.notification_frequency not in PUBLIC_NOTIFICATION_FREQUENCIES:
        raise HTTPException(status_code=422, detail="Unsupported notification frequency")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    preference = await _get_or_create_preference(session, user.id)
    preference.frequency = payload.notification_frequency
    await session.commit()
    await session.refresh(user)
    summary = await _summary(session, user)
    await session.commit()
    return summary


@router.post("/{user_id}/promote", response_model=UserSummary)
async def promote_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = UserRole.ADMIN
    user.approval_state = ApprovalState.APPROVED
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    summary = await _summary(session, user)
    await session.commit()
    return summary

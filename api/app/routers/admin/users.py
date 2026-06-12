import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.enums import ApprovalState, NotificationFrequency, UserRole
from app.models.user import NotificationPreference, User
from app.services.notification_preferences import get_or_create_notification_preference

router = APIRouter(prefix="/users", tags=["admin-users"])


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    approval_state: ApprovalState
    is_active: bool
    role: str
    email_opted_in: bool = False
    notification_frequency: NotificationFrequency


class NotificationPreferenceUpdate(BaseModel):
    email_opted_in: bool = False
    notification_frequency: NotificationFrequency = NotificationFrequency.ALL_UPDATES


class AdminProfileUpdate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = Field(default=None, max_length=200)


async def _summary(session: AsyncSession, user: User) -> UserSummary:
    preference = await get_or_create_notification_preference(session, user.id)
    return UserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        approval_state=user.approval_state,
        is_active=user.is_active,
        role=user.role.value,
        email_opted_in=preference.email_opted_in,
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
    return summary


@router.patch("/{user_id}/notifications", response_model=UserSummary)
async def update_user_notifications(
    user_id: uuid.UUID,
    payload: NotificationPreferenceUpdate,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    preference = await get_or_create_notification_preference(session, user.id)
    preference.email_opted_in = payload.email_opted_in
    preference.frequency = payload.notification_frequency
    await session.commit()
    await session.refresh(user)
    summary = await _summary(session, user)
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
    return summary


@router.post("/{user_id}/demote", response_model=UserSummary)
async def demote_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(current_admin_user),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = UserRole.USER
    await session.commit()
    await session.refresh(user)
    summary = await _summary(session, user)
    return summary


@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(current_admin_user),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(user)
    await session.commit()
    return {"ok": True}


@router.patch("/{user_id}/profile", response_model=UserSummary)
async def update_user_profile(
    user_id: uuid.UUID,
    payload: AdminProfileUpdate,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    email = payload.email.lower()
    existing = await session.execute(
        select(User).where(func.lower(User.email) == email, User.id != user_id)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Email already in use")
    user.email = email
    user.display_name = payload.display_name.strip() if payload.display_name else None
    await session.commit()
    await session.refresh(user)
    summary = await _summary(session, user)
    return summary

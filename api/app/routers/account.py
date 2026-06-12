from fastapi import APIRouter, Depends, HTTPException
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth_config import current_active_user
from app.db import get_async_session
from app.models.user import NotificationPreference, User
from app.schemas.account import AccountOut, NotificationUpdate, PasswordUpdate, ProfileUpdate
from app.services.notification_preferences import (
    get_or_create_notification_preference,
    get_or_create_notification_preference_with_status,
)

router = APIRouter(prefix="/account", tags=["account"])
password_helper = PasswordHelper()


def _account_out(user: User, preference: NotificationPreference) -> AccountOut:
    return AccountOut(
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        approval_state=user.approval_state,
        email_opted_in=preference.email_opted_in,
        notification_frequency=preference.frequency,
    )


@router.get("", response_model=AccountOut)
async def get_account(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    preference, created = await get_or_create_notification_preference_with_status(session, user.id)
    if created:
        await session.commit()
        await session.refresh(preference)
    return _account_out(user, preference)


@router.patch("/profile", response_model=AccountOut)
async def update_profile(
    payload: ProfileUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    verified, _updated_hash = password_helper.verify_and_update(
        payload.current_password, user.hashed_password
    )
    if not verified:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    email = payload.email.lower()
    existing = await session.execute(
        select(User).where(func.lower(User.email) == email, User.id != user.id)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Email is already in use")

    db_user = await session.get(User, user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.email = email
    db_user.display_name = payload.display_name.strip() if payload.display_name else None
    preference = await get_or_create_notification_preference(session, user.id)
    await session.commit()
    await session.refresh(db_user)
    return _account_out(db_user, preference)


@router.patch("/password")
async def update_password(
    payload: PasswordUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    verified, _updated_hash = password_helper.verify_and_update(
        payload.current_password,
        user.hashed_password,
    )
    if not verified:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    db_user = await session.get(User, user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.hashed_password = password_helper.hash(payload.new_password)
    await session.commit()
    return {"ok": True}


@router.patch("/notifications", response_model=AccountOut)
async def update_notifications(
    payload: NotificationUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    preference = await get_or_create_notification_preference(session, user.id)
    preference.email_opted_in = payload.email_opted_in
    preference.frequency = payload.notification_frequency
    await session.commit()
    await session.refresh(preference)
    return _account_out(user, preference)

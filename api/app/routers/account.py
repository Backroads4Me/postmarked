import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth_config import current_active_user
from app.db import get_async_session
from app.models.enums import NotificationFrequency
from app.models.user import NotificationPreference, User
from app.schemas.account import AccountOut, NotificationUpdate, PasswordUpdate, ProfileUpdate, SmsUpdate

router = APIRouter(prefix="/account", tags=["account"])
password_helper = PasswordHelper()


async def _get_or_create_preference(session: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    preference = result.scalars().first()
    if preference:
        return preference

    preference = NotificationPreference(
        user_id=user_id,
        frequency=NotificationFrequency.ALL_UPDATES,
    )
    session.add(preference)
    await session.commit()
    await session.refresh(preference)
    return preference


def _account_out(user: User, preference: NotificationPreference) -> AccountOut:
    return AccountOut(
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        approval_state=user.approval_state,
        email_opted_in=preference.email_opted_in,
        notification_frequency=preference.frequency,
        phone_number=preference.phone_number,
        sms_opted_in=preference.sms_opted_in,
    )


@router.get("", response_model=AccountOut)
async def get_account(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    preference = await _get_or_create_preference(session, user.id)
    return _account_out(user, preference)


@router.patch("/profile", response_model=AccountOut)
async def update_profile(
    payload: ProfileUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
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
    preference = await _get_or_create_preference(session, user.id)
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
    preference = await _get_or_create_preference(session, user.id)
    preference.email_opted_in = payload.email_opted_in
    preference.frequency = payload.notification_frequency
    preference.phone_number = payload.phone_number
    preference.sms_opted_in = payload.sms_opted_in and bool(payload.phone_number)
    await session.commit()
    await session.refresh(preference)
    return _account_out(user, preference)


@router.patch("/sms", response_model=AccountOut)
async def update_sms(
    payload: SmsUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    preference = await _get_or_create_preference(session, user.id)
    preference.phone_number = payload.phone_number
    preference.sms_opted_in = payload.sms_opted_in and bool(payload.phone_number)
    await session.commit()
    await session.refresh(preference)
    return _account_out(user, preference)

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.system import PreApprovedEmail, SiteConfig

router = APIRouter(tags=["admin-site-config"])


class SiteConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    require_user_approval: bool
    sms_enabled: bool


class SiteConfigUpdate(BaseModel):
    require_user_approval: bool
    sms_enabled: bool


class PreApprovedEmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str


class PreApprovedEmailsIn(BaseModel):
    emails: List[EmailStr]


async def _get_or_create_site_config(session: AsyncSession) -> SiteConfig:
    result = await session.execute(select(SiteConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        config = SiteConfig()
        session.add(config)
        await session.flush()
    return config


@router.get("/site-config", response_model=SiteConfigOut)
async def get_site_config(
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    config = await _get_or_create_site_config(session)
    await session.commit()
    return config


@router.patch("/site-config", response_model=SiteConfigOut)
async def update_site_config(
    payload: SiteConfigUpdate,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    config = await _get_or_create_site_config(session)
    config.require_user_approval = payload.require_user_approval
    config.sms_enabled = payload.sms_enabled
    await session.commit()
    await session.refresh(config)
    return config


@router.get("/pre-approved-emails", response_model=List[PreApprovedEmailOut])
async def list_pre_approved_emails(
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    rows = (await session.execute(select(PreApprovedEmail).order_by(PreApprovedEmail.created_at.asc()))).scalars().all()
    return rows


@router.post("/pre-approved-emails", response_model=List[PreApprovedEmailOut])
async def add_pre_approved_emails(
    payload: PreApprovedEmailsIn,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    added = []
    for raw_email in payload.emails:
        email = raw_email.lower().strip()
        existing = (await session.execute(
            select(PreApprovedEmail).where(PreApprovedEmail.email == email)
        )).scalar_one_or_none()
        if existing is None:
            row = PreApprovedEmail(email=email)
            session.add(row)
            await session.flush()
            added.append(row)
        else:
            added.append(existing)
    await session.commit()
    return added


@router.delete("/pre-approved-emails/{entry_id}", status_code=204)
async def delete_pre_approved_email(
    entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    row = await session.get(PreApprovedEmail, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(row)
    await session.commit()

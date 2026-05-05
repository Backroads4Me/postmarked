"""
Admin: Journey management.

V1 supports a single active journey at a time — POST /journeys/{id}/activate
flips the target row to ACTIVE and demotes any other ACTIVE journeys to PAUSED.
"""
import re
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.content import Journey
from app.models.enums import JourneyStatus
from app.models.user import User
from app.schemas.journey_admin import (
    JourneyAdminOut,
    JourneyCreate,
    JourneyUpdate,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/journeys", tags=["admin-journeys"])


def _slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return base or "journey"


async def _unique_slug(session: AsyncSession, title: str) -> str:
    base = _slugify(title)
    candidate = base
    for _ in range(8):
        existing = await session.execute(
            select(Journey.id).where(Journey.slug == candidate).limit(1)
        )
        if existing.first() is None:
            return candidate
        candidate = f"{base}-{uuid.uuid4().hex[:6]}"
    return f"{base}-{uuid.uuid4().hex}"


@router.get("", response_model=List[JourneyAdminOut])
async def list_journeys(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    result = await session.execute(
        select(Journey).order_by(Journey.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{journey_id}", response_model=JourneyAdminOut)
async def get_journey(
    journey_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    journey = await session.get(Journey, journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")
    return journey


@router.post("", response_model=JourneyAdminOut)
async def create_journey(
    journey_in: JourneyCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    slug = journey_in.slug or await _unique_slug(session, journey_in.title)
    journey = Journey(
        slug=slug,
        title=journey_in.title,
        summary=journey_in.summary,
        starts_on=journey_in.starts_on,
        ends_on=journey_in.ends_on,
        status=journey_in.status,
        visibility=journey_in.visibility,
        current_location_note=journey_in.current_location_note,
    )

    # If creating as ACTIVE, demote any existing ACTIVE journey first.
    if journey.status == JourneyStatus.ACTIVE:
        await session.execute(
            update(Journey)
            .where(Journey.status == JourneyStatus.ACTIVE)
            .values(status=JourneyStatus.PAUSED)
        )

    session.add(journey)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Journey slug already exists")

    await log_audit_event(session, user.id, "CREATE", "Journey", journey.id)
    await session.commit()
    await session.refresh(journey)
    return journey


@router.patch("/{journey_id}", response_model=JourneyAdminOut)
async def update_journey(
    journey_id: uuid.UUID,
    journey_in: JourneyUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    journey = await session.get(Journey, journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    data = journey_in.model_dump(exclude_unset=True)

    # If the patch flips this journey to ACTIVE, demote others first.
    if data.get("status") == JourneyStatus.ACTIVE and journey.status != JourneyStatus.ACTIVE:
        await session.execute(
            update(Journey)
            .where(Journey.status == JourneyStatus.ACTIVE, Journey.id != journey.id)
            .values(status=JourneyStatus.PAUSED)
        )

    for key, value in data.items():
        setattr(journey, key, value)

    await log_audit_event(session, user.id, "UPDATE", "Journey", journey.id, data)
    await session.commit()
    await session.refresh(journey)
    return journey


@router.post("/{journey_id}/activate", response_model=JourneyAdminOut)
async def activate_journey(
    journey_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """
    Mark this journey ACTIVE. Demotes the previously-active journey to PAUSED
    so there is exactly one active at a time (V1 invariant).
    """
    journey = await session.get(Journey, journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    await session.execute(
        update(Journey)
        .where(Journey.status == JourneyStatus.ACTIVE, Journey.id != journey.id)
        .values(status=JourneyStatus.PAUSED)
    )
    journey.status = JourneyStatus.ACTIVE

    await log_audit_event(session, user.id, "ACTIVATE", "Journey", journey.id)
    await session.commit()
    await session.refresh(journey)
    return journey

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, with_loader_criteria

from app.db import get_async_session
from app.models.content import Trip, Stop
from app.models.enums import StopStatus, TripStatus, Visibility
from app.schemas.trip import TripOut, TripDetailOut
from app.auth.auth_config import fastapi_users_app

router = APIRouter(prefix="/trips", tags=["trips"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)


def _is_admin(user) -> bool:
    return bool(user and getattr(getattr(user, "role", None), "value", None) == "admin")


def _public_trip_status_filter():
    return Trip.status == TripStatus.PUBLISHED


@router.get("", response_model=List[TripOut])
async def list_trips(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    query = select(Trip).options(selectinload(Trip.cover_media))
    query = query.where(_public_trip_status_filter())
    if not user:
        query = query.where(Trip.visibility == Visibility.PUBLIC)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{slug}", response_model=TripDetailOut)
async def get_trip(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    # Use with_loader_criteria so the Stop collection is filtered AT LOAD TIME.
    # Never reassign trip.stops after load: SQLAlchemy treats the relationship as
    # cascade=all,delete-orphan and an autoflush would delete the unassigned rows.
    query = select(Trip).where(Trip.slug == slug).options(
        selectinload(Trip.cover_media),
        selectinload(Trip.stops).selectinload(Stop.cover_media),
    )

    query = query.where(_public_trip_status_filter())
    stop_criteria = Stop.status == StopStatus.PUBLISHED
    if not user:
        query = query.where(Trip.visibility == Visibility.PUBLIC)
        stop_criteria = stop_criteria & (Stop.visibility == Visibility.PUBLIC)
    query = query.options(with_loader_criteria(Stop, stop_criteria))

    result = await session.execute(query)
    trip = result.scalars().first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return trip

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import selectinload
from typing import List

from app.db import get_async_session
from app.models.content import MediaAsset, Trip, Stop
from app.models.enums import Visibility
from app.schemas.trip import TripOut, TripCreate, TripUpdate
from app.auth.dependencies import current_admin_user
from app.models.user import User
from app.services.audit import log_audit_event
from app.services.media_storage import delete_media_asset_files

router = APIRouter(prefix="/trips", tags=["admin-trips"])

@router.get("", response_model=List[TripOut])
async def list_trips_admin(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    result = await session.execute(
        select(Trip)
        .options(selectinload(Trip.cover_media))
        .order_by(Trip.start_date.desc().nulls_last())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

@router.post("", response_model=TripOut)
async def create_trip_admin(
    trip_in: TripCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    trip = Trip(**trip_in.model_dump())
    session.add(trip)
    await session.flush()
    await log_audit_event(session, user.id, "CREATE", "Trip", trip.id)
    await session.commit()
    await session.refresh(trip)

    trip = (
        await session.execute(select(Trip).where(Trip.id == trip.id).options(selectinload(Trip.cover_media)))
    ).scalars().first()
    return trip

@router.patch("/{id}", response_model=TripOut)
async def update_trip_admin(
    id: str,
    trip_in: TripUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    trip = await session.get(Trip, id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    update_data = trip_in.model_dump(exclude_unset=True)
    old_cover_asset = None
    old_cover_id = trip.cover_media_id
    new_cover_id = update_data.get("cover_media_id") if "cover_media_id" in update_data else old_cover_id
    old_visibility = trip.visibility

    if "cover_media_id" in update_data and old_cover_id and old_cover_id != new_cover_id:
        old_cover_asset = await session.get(MediaAsset, old_cover_id)

    for key, value in update_data.items():
        setattr(trip, key, value)

    if "cover_media_id" in update_data and new_cover_id is not None:
        cover_asset = await session.get(MediaAsset, new_cover_id)
        if not cover_asset:
            raise HTTPException(status_code=404, detail="Cover media not found")
        cover_asset.trip_id = trip.id
        cover_asset.visibility = trip.visibility

    if old_cover_asset is not None:
        await session.delete(old_cover_asset)

    if "visibility" in update_data and trip.visibility != old_visibility:
        await session.execute(
            update(Stop)
            .where(Stop.trip_id == trip.id)
            .values(visibility=trip.visibility)
        )
        await session.execute(
            update(MediaAsset)
            .where(
                MediaAsset.trip_id == trip.id,
                MediaAsset.stop_id.is_(None),
                MediaAsset.post_id.is_(None),
            )
            .values(visibility=trip.visibility)
        )

    await log_audit_event(session, user.id, "UPDATE", "Trip", trip.id, update_data)
    await session.commit()
    if old_cover_asset is not None:
        delete_media_asset_files(old_cover_asset)
    await session.refresh(trip)

    # Eager-load cover_media for response serialization
    trip = (
        await session.execute(select(Trip).where(Trip.id == id).options(selectinload(Trip.cover_media)))
    ).scalars().first()
    return trip

@router.delete("/{id}")
async def delete_trip_admin(
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    trip = await session.get(Trip, id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    trip_owned_media_result = await session.execute(
        select(MediaAsset).where(
            or_(MediaAsset.trip_id == trip.id, MediaAsset.id == trip.cover_media_id),
            MediaAsset.stop_id.is_(None),
            MediaAsset.post_id.is_(None),
            MediaAsset.attached_to.is_(None),
        )
    )
    trip_owned_media = list(trip_owned_media_result.scalars().unique())

    # Break the cover FK before deleting the asset row it points at.
    trip.cover_media_id = None
    for asset in trip_owned_media:
        await session.delete(asset)

    await session.execute(delete(Stop).where(Stop.trip_id == trip.id))
    await session.delete(trip)
    await log_audit_event(session, user.id, "DELETE", "Trip", trip.id)
    await session.commit()
    for asset in trip_owned_media:
        delete_media_asset_files(asset)
    return {"ok": True}

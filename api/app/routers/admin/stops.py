from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import List

from app.db import get_async_session
from app.models.content import Stop, Trip
from app.schemas.stop import StopOut, StopBulkUpdate, StopCreate, StopUpdate
from app.auth.dependencies import current_admin_user
from app.models.enums import Visibility
from app.models.user import User
from app.services.audit import log_audit_event
from app.services.timezone import timezone_for_coords

router = APIRouter(prefix="/stops", tags=["admin-stops"])


@router.get("", response_model=List[StopOut])
async def list_stops_admin(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    result = await session.execute(select(Stop).order_by(Stop.start_date.desc()))
    return result.scalars().all()


@router.post("", response_model=StopOut)
async def create_stop_admin(
    stop_in: StopCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    data = stop_in.model_dump()
    lat = data.pop("latitude")
    lon = data.pop("longitude")
    trip = await session.get(Trip, data["trip_id"])
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    requested_visibility = data.pop("visibility", None)
    data["visibility"] = (
        Visibility.PRIVATE
        if trip.visibility == Visibility.PRIVATE
        else requested_visibility or trip.visibility
    )
    stop = Stop(**data, location=f"POINT({lon} {lat})", timezone_id=timezone_for_coords(lat, lon))
    session.add(stop)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A stop with slug '{stop_in.slug}' already exists in this trip.",
        )
    await log_audit_event(session, user.id, "CREATE", "Stop", stop.id)
    await session.commit()
    await session.refresh(stop)
    return stop


@router.post("/bulk")
async def bulk_update_stops_admin(
    bulk_in: StopBulkUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    result = await session.execute(select(Stop).where(Stop.id.in_(bulk_in.stop_ids)))
    stops = list(result.scalars().all())
    found_ids = {stop.id for stop in stops}
    missing_ids = [str(stop_id) for stop_id in bulk_in.stop_ids if stop_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Stop not found: {', '.join(missing_ids)}")

    if bulk_in.delete:
        for stop in stops:
            await session.delete(stop)
            await log_audit_event(session, user.id, "DELETE", "Stop", stop.id, {"bulk": True})
        await session.commit()
        return {"ok": True, "updated": 0, "deleted": len(stops)}

    update_data = bulk_in.model_dump(exclude={"stop_ids", "delete"}, exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="Choose a status or type to update.")

    if update_data.get("visibility") == Visibility.PUBLIC:
        trip_ids = {stop.trip_id for stop in stops}
        trips = (await session.execute(select(Trip).where(Trip.id.in_(trip_ids)))).scalars().all()
        private_trips = [trip.title for trip in trips if trip.visibility == Visibility.PRIVATE]
        if private_trips:
            raise HTTPException(
                status_code=422,
                detail="Private trips cannot have public stops.",
            )

    for stop in stops:
        for key, value in update_data.items():
            setattr(stop, key, value)
        await log_audit_event(session, user.id, "UPDATE", "Stop", stop.id, {"bulk": True, **update_data})

    await session.commit()
    return {"ok": True, "updated": len(stops), "deleted": 0}


@router.patch("/{id}", response_model=StopOut)
async def update_stop_admin(
    id: str,
    stop_in: StopUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    stop = await session.get(Stop, id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    update_data = stop_in.model_dump(exclude_unset=True)
    if update_data.get("visibility") == Visibility.PUBLIC:
        trip = await session.get(Trip, stop.trip_id)
        if trip and trip.visibility == Visibility.PRIVATE:
            raise HTTPException(status_code=422, detail="Private trips cannot have public stops.")

    # Lat/lon are not direct columns; rebuild the PostGIS POINT.
    new_lat = update_data.pop("latitude", None)
    new_lon = update_data.pop("longitude", None)
    if new_lat is not None or new_lon is not None:
        if new_lat is None or new_lon is None:
            raise HTTPException(
                status_code=422,
                detail="latitude and longitude must be supplied together when updating location.",
            )
        stop.location = f"POINT({new_lon} {new_lat})"
        stop.timezone_id = timezone_for_coords(new_lat, new_lon)

    for key, value in update_data.items():
        setattr(stop, key, value)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A stop with slug '{update_data.get('slug')}' already exists in this trip.",
        )

    await log_audit_event(session, user.id, "UPDATE", "Stop", stop.id, update_data)
    await session.commit()
    await session.refresh(stop)
    return stop


@router.delete("/{id}")
async def delete_stop_admin(
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    stop = await session.get(Stop, id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    await session.delete(stop)
    await log_audit_event(session, user.id, "DELETE", "Stop", stop.id)
    await session.commit()
    return {"ok": True}

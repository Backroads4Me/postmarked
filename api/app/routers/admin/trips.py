from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.db import get_async_session
from app.models.content import Trip, Stop, PlannedStop
from app.schemas.trip import TripOut, TripCreate, TripUpdate
from app.auth.dependencies import current_admin_user
from app.models.user import User
from app.services.audit import log_audit_event

router = APIRouter(prefix="/trips", tags=["admin-trips"])

@router.get("", response_model=List[TripOut])
async def list_trips_admin(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user)
):
    result = await session.execute(select(Trip).order_by(Trip.start_date.desc().nulls_last()))
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
    for key, value in update_data.items():
        setattr(trip, key, value)
        
    await log_audit_event(session, user.id, "UPDATE", "Trip", trip.id, update_data)
    await session.commit()
    await session.refresh(trip)
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
        
    await session.execute(delete(Stop).where(Stop.trip_id == trip.id))
    await session.execute(delete(PlannedStop).where(PlannedStop.trip_id == trip.id))
    await session.delete(trip)
    await log_audit_event(session, user.id, "DELETE", "Trip", trip.id)
    await session.commit()
    return {"ok": True}

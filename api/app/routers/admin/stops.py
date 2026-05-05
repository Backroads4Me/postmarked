from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import List

from app.db import get_async_session
from app.models.content import Stop
from app.schemas.stop import StopOut, StopCreate, StopUpdate
from app.auth.dependencies import current_admin_user
from app.models.user import User
from app.services.audit import log_audit_event

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
    stop = Stop(**data, location=f"POINT({lon} {lat})")
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

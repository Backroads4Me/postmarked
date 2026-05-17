import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.content import PointOfInterest, Stop
from app.models.user import User
from app.schemas.poi import POICreate, POIOut, POIUpdate
from app.services.audit import log_audit_event

router = APIRouter(tags=["admin-pois"])


async def _poi_out(poi: PointOfInterest, session: AsyncSession) -> POIOut:
    point = cast(PointOfInterest.location, Geometry(geometry_type="POINT", srid=4326))
    row = (await session.execute(
        select(func.ST_Y(point).label("lat"), func.ST_X(point).label("lon"))
        .where(PointOfInterest.id == poi.id)
    )).first()
    return POIOut(
        id=poi.id,
        stop_id=poi.stop_id,
        label=poi.label,
        poi_type=poi.poi_type,
        notes=poi.notes,
        google_maps_url=poi.google_maps_url,
        latitude=row.lat if row else 0.0,
        longitude=row.lon if row else 0.0,
    )


@router.get("/stops/{stop_id}/pois", response_model=List[POIOut])
async def list_pois(
    stop_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    stop = await session.get(Stop, stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    rows = (await session.execute(
        select(PointOfInterest).where(PointOfInterest.stop_id == stop_id)
    )).scalars().all()

    return [await _poi_out(poi, session) for poi in rows]


@router.post("/stops/{stop_id}/pois", response_model=POIOut)
async def create_poi(
    stop_id: uuid.UUID,
    poi_in: POICreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    stop = await session.get(Stop, stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    poi = PointOfInterest(
        stop_id=stop_id,
        label=poi_in.label,
        poi_type=poi_in.poi_type,
        notes=poi_in.notes,
        google_maps_url=poi_in.google_maps_url,
        location=f"POINT({poi_in.longitude} {poi_in.latitude})",
    )
    session.add(poi)
    await session.flush()
    await log_audit_event(session, user.id, "CREATE", "PointOfInterest", poi.id)
    await session.commit()
    await session.refresh(poi)
    return await _poi_out(poi, session)


@router.patch("/stops/{stop_id}/pois/{poi_id}", response_model=POIOut)
async def update_poi(
    stop_id: uuid.UUID,
    poi_id: uuid.UUID,
    poi_in: POIUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    poi = await session.get(PointOfInterest, poi_id)
    if not poi or poi.stop_id != stop_id:
        raise HTTPException(status_code=404, detail="POI not found")

    update_data = poi_in.model_dump(exclude_unset=True)
    new_lat = update_data.pop("latitude", None)
    new_lon = update_data.pop("longitude", None)
    if new_lat is not None or new_lon is not None:
        if new_lat is None or new_lon is None:
            raise HTTPException(
                status_code=422,
                detail="latitude and longitude must be supplied together when updating location.",
            )
        poi.location = f"POINT({new_lon} {new_lat})"

    for key, value in update_data.items():
        setattr(poi, key, value)

    await log_audit_event(session, user.id, "UPDATE", "PointOfInterest", poi.id, update_data)
    await session.commit()
    await session.refresh(poi)
    return await _poi_out(poi, session)


@router.delete("/stops/{stop_id}/pois/{poi_id}")
async def delete_poi(
    stop_id: uuid.UUID,
    poi_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    poi = await session.get(PointOfInterest, poi_id)
    if not poi or poi.stop_id != stop_id:
        raise HTTPException(status_code=404, detail="POI not found")

    await session.delete(poi)
    await log_audit_event(session, user.id, "DELETE", "PointOfInterest", poi.id)
    await session.commit()
    return {"ok": True}

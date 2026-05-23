from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List

from app.db import get_async_session
from app.models.content import Trip, Stop
from app.schemas.search import SearchResult
from app.models.enums import StopStatus, TripStatus, Visibility
from app.auth.auth_config import fastapi_users_app

router = APIRouter(prefix="/search", tags=["search"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)

@router.get("", response_model=List[SearchResult])
async def global_search(
    q: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    if not q or len(q) < 2:
        return []

    results = []
    
    # 1. Search Trips
    query_trips = select(Trip).where(
        Trip.status == TripStatus.PUBLISHED,
        or_(
            Trip.title.ilike(f"%{q}%"),
            Trip.summary.ilike(f"%{q}%")
        )
    ).limit(10)
    if not user:
        query_trips = query_trips.where(Trip.visibility == Visibility.PUBLIC)
    res_trips = await session.execute(query_trips)
    for t in res_trips.scalars().all():
        results.append(SearchResult(
            entity_type="trip",
            id=t.id,
            title=t.title,
            summary=t.summary,
            slug=f"/trips/{t.slug}"
        ))

    # 2. Search Stops
    query_stops = select(Stop, Trip.slug.label("trip_slug")).join(Trip, Stop.trip_id == Trip.id).where(
        Trip.status == TripStatus.PUBLISHED,
        Stop.status == StopStatus.PUBLISHED,
        or_(
            Stop.title.ilike(f"%{q}%"),
            Stop.summary.ilike(f"%{q}%")
        )
    ).limit(10)
    if not user:
        query_stops = query_stops.where(Trip.visibility == Visibility.PUBLIC, Stop.visibility == Visibility.PUBLIC)
    res_stops = await session.execute(query_stops)
    for s, trip_slug in res_stops.all():
        results.append(SearchResult(
            entity_type="stop",
            id=s.id,
            title=s.title,
            summary=s.summary,
            slug=f"/trips/{trip_slug}/stops/{s.slug}"
        ))

    return results

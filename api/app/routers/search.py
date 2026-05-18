from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List

from app.db import get_async_session
from app.models.content import Trip, Stop
from app.schemas.search import SearchResult
from app.models.enums import StopStatus, TripStatus, Visibility

router = APIRouter(prefix="/search", tags=["search"])

@router.get("", response_model=List[SearchResult])
async def global_search(
    q: str,
    session: AsyncSession = Depends(get_async_session)
):
    if not q or len(q) < 2:
        return []

    results = []
    
    # 1. Search Trips
    query_trips = select(Trip).where(
        Trip.visibility == Visibility.PUBLIC,
        Trip.status.notin_([TripStatus.DRAFT, TripStatus.ARCHIVED]),
        or_(
            Trip.title.ilike(f"%{q}%"),
            Trip.summary.ilike(f"%{q}%")
        )
    ).limit(10)
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
    query_stops = select(Stop).join(Trip, Stop.trip_id == Trip.id).where(
        Trip.visibility == Visibility.PUBLIC,
        Trip.status.notin_([TripStatus.DRAFT, TripStatus.ARCHIVED]),
        Stop.status.notin_([StopStatus.DRAFT, StopStatus.ARCHIVED]),
        or_(
            Stop.title.ilike(f"%{q}%"),
            Stop.summary.ilike(f"%{q}%")
        )
    ).limit(10)
    res_stops = await session.execute(query_stops)
    for s in res_stops.scalars().all():
        results.append(SearchResult(
            entity_type="stop",
            id=s.id,
            title=s.title,
            summary=s.summary,
            slug=f"/trips/search-redirect?stop={s.id}" # Simplified routing payload
        ))

    return results

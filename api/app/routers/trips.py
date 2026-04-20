from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_async_session
from app.models.content import Trip, Stop
from app.models.enums import Visibility
from app.schemas.trip import TripOut, TripDetailOut
from app.auth.auth_config import fastapi_users_app
from app.schemas.stop import StopOut

router = APIRouter(prefix="/trips", tags=["trips"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)

@router.get("", response_model=List[TripOut])
async def list_trips(
    session: AsyncSession = Depends(get_async_session),
    user = Depends(current_user_optional)
):
    query = select(Trip).options(selectinload(Trip.cover_media))
    
    # Simple visibility logic
    if not user or user.role.value != "admin":
        query = query.where(Trip.visibility == Visibility.PUBLIC)
        
    result = await session.execute(query)
    trips = result.scalars().all()
    # GeoAlchemy handles objects, we just ignore geography serialization for this lightweight API or convert it manually 
    return trips

@router.get("/{slug}", response_model=TripDetailOut)
async def get_trip(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(current_user_optional)
):
    query = select(Trip).where(Trip.slug == slug).options(
        selectinload(Trip.cover_media),
        selectinload(Trip.stops).selectinload(Stop.cover_media)
    )
    
    if not user or user.role.value != "admin":
        query = query.where(Trip.visibility == Visibility.PUBLIC)
        
    result = await session.execute(query)
    trip = result.scalars().first()
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    # Filter stops by visibility as well
    if not user or user.role.value != "admin":
        trip.stops = [s for s in trip.stops if s.visibility == Visibility.PUBLIC]
        
    return trip

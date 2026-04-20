from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_async_session
from app.models.content import Stop
from app.models.enums import Visibility
from app.schemas.stop import StopOut, StopDetailOut
from app.auth.auth_config import fastapi_users_app

router = APIRouter(prefix="/stops", tags=["stops"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)

@router.get("/{slug}", response_model=StopDetailOut)
async def get_stop(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(current_user_optional)
):
    query = select(Stop).where(Stop.slug == slug).options(
        selectinload(Stop.cover_media),
        selectinload(Stop.trip)
    )
    
    if not user or user.role.value != "admin":
        query = query.where(Stop.visibility == Visibility.PUBLIC)
        
    result = await session.execute(query)
    stop = result.scalars().first()
    
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
        
    # Apply effective visibility (min(asset.visibility, parent.visibility)) natively using the loaded trip
    if not user or user.role.value != "admin":
        if stop.trip and stop.trip.visibility != Visibility.PUBLIC:
            raise HTTPException(status_code=404, detail="Stop not found")
            
    return stop

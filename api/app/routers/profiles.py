from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_async_session
from app.models.profile import RvProfile, TravelerProfile
from app.schemas.profile import CombinedProfilesOut, RvProfileOut, TravelerProfileOut
from app.auth.auth_config import fastapi_users_app
from app.models.enums import Visibility

router = APIRouter(prefix="/profiles", tags=["profiles"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)

@router.get("", response_model=CombinedProfilesOut)
async def get_profiles(
    session: AsyncSession = Depends(get_async_session),
    user = Depends(current_user_optional)
):
    rv_query = select(RvProfile).options(selectinload(RvProfile.cover_media))
    tr_query = select(TravelerProfile).options(selectinload(TravelerProfile.cover_media))
    
    if not user or user.role.value != "admin":
        rv_query = rv_query.where(RvProfile.visibility == Visibility.PUBLIC)
        tr_query = tr_query.where(TravelerProfile.visibility == Visibility.PUBLIC)
        
    rv_res = await session.execute(rv_query)
    tr_res = await session.execute(tr_query)
    
    rv = rv_res.scalars().first()
    tr = tr_res.scalars().first()
    
    return CombinedProfilesOut(
        rv=RvProfileOut.model_validate(rv) if rv else None,
        traveler=TravelerProfileOut.model_validate(tr) if tr else None
    )

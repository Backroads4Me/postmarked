from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
    stop = Stop(**stop_in.model_dump())
    session.add(stop)
    await session.flush()
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
    for key, value in update_data.items():
        setattr(stop, key, value)
        
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

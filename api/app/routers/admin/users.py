import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.enums import ApprovalState
from app.models.user import User

router = APIRouter(prefix="/users", tags=["admin-users"])


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    approval_state: ApprovalState
    is_active: bool
    role: str


@router.get("", response_model=List[UserSummary])
async def list_users(
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    query = select(User)
    if status == "pending":
        query = query.where(User.approval_state == ApprovalState.PENDING)
    elif status == "approved":
        query = query.where(User.approval_state == ApprovalState.APPROVED)
    rows = (await session.execute(query.order_by(User.created_at.asc()))).scalars().all()
    return [
        UserSummary(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            approval_state=u.approval_state,
            is_active=u.is_active,
            role=u.role.value,
        )
        for u in rows
    ]


@router.post("/{user_id}/approve", response_model=UserSummary)
async def approve_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.approval_state = ApprovalState.APPROVED
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    return UserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        approval_state=user.approval_state,
        is_active=user.is_active,
        role=user.role.value,
    )


@router.post("/{user_id}/reject", response_model=UserSummary)
async def reject_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_admin_user),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.approval_state = ApprovalState.REJECTED
    user.is_active = False
    await session.commit()
    await session.refresh(user)
    return UserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        approval_state=user.approval_state,
        is_active=user.is_active,
        role=user.role.value,
    )

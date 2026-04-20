from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
import uuid

from app.db import get_async_session
from app.auth.dependencies import current_approved_user
from app.models.user import User
from app.models.system import Comment, Like
from app.schemas.social import CommentCreate, CommentOut, LikeToggle

router = APIRouter(prefix="/social", tags=["social"])

@router.get("/comments/{entity_type}/{entity_id}", response_model=List[CommentOut])
async def list_comments(
    entity_type: str,
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    query = select(Comment).where(
        Comment.entity_type == entity_type,
        Comment.entity_id == entity_id,
        Comment.is_moderated == False
    ).order_by(Comment.created_at.asc())
    
    result = await session.execute(query)
    return result.scalars().all()

@router.post("/comments", response_model=CommentOut)
async def create_comment(
    comment_in: CommentCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_approved_user)
):
    comment = Comment(
        **comment_in.model_dump(),
        user_id=user.id
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return comment

@router.post("/likes")
async def toggle_like(
    like_in: LikeToggle,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_approved_user)
):
    # Check if already liked
    query = select(Like).where(
        Like.entity_type == like_in.entity_type,
        Like.entity_id == like_in.entity_id,
        Like.user_id == user.id
    )
    result = await session.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        await session.delete(existing)
        await session.commit()
        return {"liked": False}
    else:
        new_like = Like(
            entity_type=like_in.entity_type,
            entity_id=like_in.entity_id,
            user_id=user.id
        )
        session.add(new_like)
        await session.commit()
        return {"liked": True}

@router.get("/likes/{entity_type}/{entity_id}/count")
async def get_like_count(
    entity_type: str,
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    query = select(Like).where(
        Like.entity_type == entity_type,
        Like.entity_id == entity_id
    )
    result = await session.execute(query)
    return {"count": len(result.scalars().all())}

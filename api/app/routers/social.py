"""
Social: comments and likes.

All read and write paths enforce min(self, parent) visibility on the target.
A target the caller cannot see returns 404 (not 403) to avoid leaking existence.
"""
import html
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth_config import fastapi_users_app
from app.auth.dependencies import current_approved_user
from app.db import get_async_session
from app.models.system import Comment, Like
from app.models.user import User
from app.schemas.social import COMMENT_BODY_MAX_LEN, CommentCreate, CommentOut, LikeToggle
from app.services.visibility import (
    ALLOWED_TARGET_KINDS,
    is_visible_to_user,
    load_target_with_visibility,
)

router = APIRouter(prefix="/social", tags=["social"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)


async def _assert_target_visible(
    session: AsyncSession,
    target_kind: str,
    target_id: uuid.UUID,
    user,
):
    if target_kind not in ALLOWED_TARGET_KINDS:
        raise HTTPException(status_code=404, detail="Target not found")
    loaded = await load_target_with_visibility(session, target_kind, target_id)
    if not loaded:
        raise HTTPException(status_code=404, detail="Target not found")
    target, eff_vis = loaded
    # Effective visibility was already computed against the parent.
    if not is_visible_to_user(eff_vis, None, user):
        raise HTTPException(status_code=404, detail="Target not found")
    return target


def _sanitize_body(body: str) -> str:
    """
    Plain-text sanitization: HTML-escape and trim. Markdown rendering is the
    reader's responsibility; we never store raw HTML.
    """
    return html.escape(body.strip())


@router.get("/comments/{target_kind}/{target_id}", response_model=List[CommentOut])
async def list_comments(
    target_kind: str,
    target_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    # Optional auth: anonymous can read public-target comments; private-target
    # comments are 404 unless the caller can see the target.
    user=Depends(current_user_optional),
):
    await _assert_target_visible(session, target_kind, target_id, user)

    query = (
        select(Comment, User.display_name)
        .join(User, Comment.author_id == User.id)
        .where(
            Comment.target_kind == target_kind,
            Comment.target_id == target_id,
            Comment.deleted_at.is_(None),
        )
        .order_by(Comment.created_at.asc())
    )
    rows = (await session.execute(query)).all()

    out: list[CommentOut] = []
    for comment, display_name in rows:
        out.append(
            CommentOut(
                id=comment.id,
                target_kind=comment.target_kind,
                target_id=comment.target_id,
                body=comment.body,
                author_id=comment.author_id,
                author_display_name=display_name or "Traveler",
                created_at=comment.created_at,
                updated_at=comment.updated_at,
            )
        )
    return out


@router.post("/comments", response_model=CommentOut)
async def create_comment(
    comment_in: CommentCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_approved_user),
):
    await _assert_target_visible(session, comment_in.target_kind, comment_in.target_id, user)

    sanitized = _sanitize_body(comment_in.body)
    if not sanitized:
        raise HTTPException(status_code=422, detail="Comment body cannot be empty")
    if len(sanitized) > COMMENT_BODY_MAX_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"Comment body exceeds {COMMENT_BODY_MAX_LEN} characters",
        )

    comment = Comment(
        target_kind=comment_in.target_kind,
        target_id=comment_in.target_id,
        body=sanitized,
        author_id=user.id,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    return CommentOut(
        id=comment.id,
        target_kind=comment.target_kind,
        target_id=comment.target_id,
        body=comment.body,
        author_id=comment.author_id,
        author_display_name=user.display_name or "Traveler",
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.post("/likes")
async def toggle_like(
    like_in: LikeToggle,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_approved_user),
):
    await _assert_target_visible(session, like_in.target_kind, like_in.target_id, user)

    existing_q = select(Like).where(
        Like.author_id == user.id,
        Like.target_kind == like_in.target_kind,
        Like.target_id == like_in.target_id,
    )
    existing = (await session.execute(existing_q)).scalar_one_or_none()

    if existing:
        await session.delete(existing)
        await session.commit()
        return {"liked": False}

    new_like = Like(
        author_id=user.id,
        target_kind=like_in.target_kind,
        target_id=like_in.target_id,
    )
    session.add(new_like)
    try:
        await session.commit()
    except IntegrityError:
        # Race with another request — treat as already-liked
        await session.rollback()
        return {"liked": True}
    return {"liked": True}


@router.get("/likes/{target_kind}/{target_id}/status")
async def get_like_status(
    target_kind: str,
    target_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    """Returns like count and whether the current user has liked the target."""
    await _assert_target_visible(session, target_kind, target_id, user)

    count_result = await session.execute(
        select(func.count(Like.id)).where(
            Like.target_kind == target_kind,
            Like.target_id == target_id,
        )
    )
    count = count_result.scalar_one()

    liked = None
    if user:
        existing = (await session.execute(
            select(Like).where(
                Like.author_id == user.id,
                Like.target_kind == target_kind,
                Like.target_id == target_id,
            )
        )).scalar_one_or_none()
        liked = existing is not None

    return {"count": count, "liked": liked}


@router.get("/likes/{target_kind}/{target_id}/count")
async def get_like_count(
    target_kind: str,
    target_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    await _assert_target_visible(session, target_kind, target_id, user)

    result = await session.execute(
        select(func.count(Like.id)).where(
            Like.target_kind == target_kind,
            Like.target_id == target_id,
        )
    )
    return {"count": result.scalar_one()}

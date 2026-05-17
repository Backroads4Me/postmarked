"""
Admin posts and current-stop management.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.content import MediaAsset, PointOfInterest, Post, Stop
from app.models.enums import StopStatus, Visibility
from app.models.user import User
from app.schemas.post import PostCreate, PostOut, PostUpdate
from app.services.audit import log_audit_event

router = APIRouter(tags=["admin-posts"])


# ── Posts ────────────────────────────────────────────────────────────────

@router.get("/posts", response_model=List[PostOut])
async def list_posts(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.media), selectinload(Post.poi))
        .order_by(Post.posted_at.desc())
    )
    return result.scalars().all()


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return base or "post"


async def _unique_post_slug(session: AsyncSession, title: str) -> str:
    """
    Build a globally-unique post slug. Post.slug has a global unique index;
    we suffix with a short uuid until we find an unused slug. Bounded retries.
    """
    base = _slugify(title)
    candidate = base
    for attempt in range(8):
        existing = await session.execute(select(Post.id).where(Post.slug == candidate).limit(1))
        if existing.first() is None:
            return candidate
        candidate = f"{base}-{uuid.uuid4().hex[:6]}"
    # Fall back to a guaranteed-unique full uuid suffix.
    return f"{base}-{uuid.uuid4().hex}"


@router.post("/posts", response_model=PostOut)
async def create_post(
    post_in: PostCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    posted_at = post_in.posted_at or datetime.now(timezone.utc)
    visibility = Visibility(post_in.visibility)
    slug = await _unique_post_slug(session, post_in.title)

    # Validate poi_id belongs to the given stop
    if post_in.poi_id and post_in.stop_id:
        poi = await session.get(PointOfInterest, post_in.poi_id)
        if not poi or poi.stop_id != post_in.stop_id:
            raise HTTPException(status_code=422, detail="poi_id does not belong to the given stop")

    post = Post(
        trip_id=post_in.trip_id,
        stop_id=post_in.stop_id,
        slug=slug,
        title=post_in.title,
        body=post_in.body,
        posted_at=posted_at,
        visibility=visibility,
        post_type=post_in.post_type,
        activity_type=post_in.activity_type,
        summary=post_in.summary,
        activity_started_at=post_in.activity_started_at,
        activity_ended_at=post_in.activity_ended_at,
        poi_id=post_in.poi_id,
    )
    session.add(post)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Could not allocate a unique post slug")

    # Attach any uploaded media. Each asset inherits this post's visibility
    # (subject to min(self, parent) at read time). Caller may pass an empty list.
    if post_in.media_ids:
        attached = 0
        for media_id in post_in.media_ids:
            asset = await session.get(MediaAsset, media_id)
            if not asset:
                continue
            asset.post_id = post.id
            asset.stop_id = post.stop_id  # so stop-scoped queries pick it up too
            asset.visibility = visibility
            attached += 1

    await log_audit_event(session, user.id, "CREATE", "Post", post.id)
    await session.commit()
    await session.refresh(post)
    await session.refresh(post, ["poi"])
    return post


@router.patch("/posts/{post_id}", response_model=PostOut)
async def update_post(
    post_id: uuid.UUID,
    post_in: PostUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    result = await session.execute(
        select(Post)
        .where(Post.id == post_id)
        .options(selectinload(Post.media), selectinload(Post.poi))
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    update_data = post_in.model_dump(exclude_unset=True)
    if "visibility" in update_data:
        update_data["visibility"] = Visibility(update_data["visibility"])
    for key, value in update_data.items():
        setattr(post, key, value)

    await log_audit_event(session, user.id, "UPDATE", "Post", post.id, update_data)
    await session.commit()
    await session.refresh(post)
    return post


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    await session.delete(post)
    await log_audit_event(session, user.id, "DELETE", "Post", post.id)
    await session.commit()
    return {"ok": True}


# ── Current Stop ─────────────────────────────────────────────────────────

class SetCurrentStopRequest(BaseModel):
    stop_id: uuid.UUID


@router.post("/current-stop")
async def set_current_stop(
    req: SetCurrentStopRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """Mark a stop as the current location. Unmarks all other stops."""
    stop = await session.get(Stop, req.stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    await session.execute(
        update(Stop)
        .where(Stop.is_current == True)
        .values(is_current=False)
    )
    await session.execute(
        update(Stop)
        .where(Stop.status == StopStatus.ACTIVE)
        .values(status=StopStatus.PUBLISHED)
    )
    stop.is_current = True
    stop.status = StopStatus.ACTIVE

    await log_audit_event(session, user.id, "SET_CURRENT_STOP", "Stop", stop.id)
    await session.commit()

    return {
        "ok": True,
        "current_stop": {
            "id": str(stop.id),
            "title": stop.title,
            "slug": stop.slug,
        },
    }


@router.get("/current-stop")
async def get_current_stop(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """Get the currently marked stop."""
    result = await session.execute(
        select(Stop).where(Stop.is_current == True)
    )
    stop = result.scalars().first()
    if not stop:
        return {"current_stop": None}
    return {
        "current_stop": {
            "id": str(stop.id),
            "title": stop.title,
            "slug": stop.slug,
            "place_name": stop.place_name,
            "start_date": stop.start_date.isoformat() if stop.start_date else None,
        },
    }

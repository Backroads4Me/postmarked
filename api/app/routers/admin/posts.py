"""
Admin posts and current-stop management.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.content import MediaAsset, PointOfInterest, Post, Stop, Trip
from app.models.enums import PostStatus, PostType, StopStatus, TripStatus, Visibility
from app.models.user import User
from app.schemas.post import PostCreate, PostOut, PostUpdate
from app.services.audit import log_audit_event
from app.services.media_storage import delete_media_asset_files

router = APIRouter(tags=["admin-posts"])


# ── Posts ────────────────────────────────────────────────────────────────

@router.get("/posts", response_model=List[PostOut])
async def list_posts(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.media), selectinload(Post.poi))
        .order_by(Post.posted_at.desc())
        .offset(skip)
        .limit(limit)
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


def _should_notify(post: Post) -> bool:
    return post.status == PostStatus.PUBLISHED


def _queue_post_notification(post_id: uuid.UUID) -> None:
    import logging
    from app.tasks import dispatch_post_notification

    logger = logging.getLogger(__name__)
    try:
        dispatch_post_notification.delay(str(post_id))
        logger.info("[notify] Queued post notification for post %s", post_id)
    except Exception:
        logger.exception("[notify] Failed to enqueue post notification for post %s", post_id)


class AttachPostMediaRequest(BaseModel):
    media_ids: List[uuid.UUID]


async def _attach_media_to_post(
    session: AsyncSession,
    post: Post,
    media_ids: List[uuid.UUID],
    visibility: Visibility,
) -> int:
    attached = 0
    for media_id in media_ids:
        asset = await session.get(MediaAsset, media_id)
        if not asset:
            continue
        asset.post_id = post.id
        asset.stop_id = post.stop_id
        asset.trip_id = post.trip_id
        asset.visibility = visibility
        attached += 1
    return attached


@router.post("/posts", response_model=PostOut)
async def create_post(
    post_in: PostCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    posted_at = post_in.posted_at or datetime.now(timezone.utc)
    visibility = Visibility(post_in.visibility)
    slug = await _unique_post_slug(session, post_in.title)

    stop = None
    if post_in.stop_id:
        stop = await session.get(Stop, post_in.stop_id)
        if not stop:
            raise HTTPException(status_code=422, detail="stop_id does not exist")

    # Validate poi_id belongs to the given stop
    if post_in.poi_id and post_in.stop_id:
        poi = await session.get(PointOfInterest, post_in.poi_id)
        if not poi or poi.stop_id != post_in.stop_id:
            raise HTTPException(status_code=422, detail="poi_id does not belong to the given stop")

    post = Post(
        trip_id=post_in.trip_id or (stop.trip_id if stop else None),
        stop_id=post_in.stop_id,
        slug=slug,
        title=post_in.title,
        body=post_in.body,
        posted_at=posted_at,
        visibility=visibility,
        status=post_in.status,
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
        await _attach_media_to_post(session, post, post_in.media_ids, visibility)

    await log_audit_event(session, user.id, "CREATE", "Post", post.id)
    await session.commit()
    if _should_notify(post):
        _queue_post_notification(post.id)

    result = await session.execute(
        select(Post)
        .where(Post.id == post.id)
        .options(selectinload(Post.media), selectinload(Post.poi))
    )
    return result.scalars().one()


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
    was_notifiable = _should_notify(post)

    update_data = post_in.model_dump(exclude_unset=True)
    if "visibility" in update_data:
        update_data["visibility"] = Visibility(update_data["visibility"])
    if "status" in update_data and update_data["status"] == PostStatus.PUBLISHED:
        post.posted_at = post.posted_at or datetime.now(timezone.utc)
    for key, value in update_data.items():
        setattr(post, key, value)

    await log_audit_event(session, user.id, "UPDATE", "Post", post.id, update_data)
    await session.commit()
    await session.refresh(post)
    if not was_notifiable and _should_notify(post):
        _queue_post_notification(post.id)
    return post


@router.post("/posts/{post_id}/media", response_model=PostOut)
async def attach_post_media(
    post_id: uuid.UUID,
    req: AttachPostMediaRequest,
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

    visibility = Visibility(post.visibility)
    attached = await _attach_media_to_post(session, post, req.media_ids, visibility)
    await log_audit_event(session, user.id, "ATTACH_MEDIA", "Post", post.id, {"attached_media_count": attached})
    await session.commit()

    result = await session.execute(
        select(Post)
        .where(Post.id == post.id)
        .options(selectinload(Post.media), selectinload(Post.poi))
    )
    return result.scalars().one()


class ReorderPostMediaRequest(BaseModel):
    media_ids: List[uuid.UUID]


@router.put("/posts/{post_id}/media/order")
async def reorder_post_media(
    post_id: uuid.UUID,
    req: ReorderPostMediaRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    for index, media_id in enumerate(req.media_ids):
        asset = await session.get(MediaAsset, media_id)
        if asset and asset.post_id == post_id:
            asset.sort_order = index

    await log_audit_event(session, user.id, "REORDER_MEDIA", "Post", post_id)
    await session.commit()
    return {"ok": True}


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    media_result = await session.execute(select(MediaAsset).where(MediaAsset.post_id == post_id))
    attached_media = list(media_result.scalars().all())
    for asset in attached_media:
        await session.delete(asset)

    await session.delete(post)
    await log_audit_event(
        session,
        user.id,
        "DELETE",
        "Post",
        post.id,
        {"deleted_media_count": len(attached_media)},
    )
    await session.commit()
    for asset in attached_media:
        delete_media_asset_files(asset)
    return {"ok": True, "deleted_media_count": len(attached_media)}


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
    stop.is_current = True
    if stop.status != StopStatus.ARCHIVED:
        stop.status = StopStatus.PUBLISHED

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
    """Get the marked current stop, or infer it from today's published itinerary."""
    result = await session.execute(
        select(Stop).where(Stop.is_current == True)
    )
    stop = result.scalars().first()
    if not stop:
        today = datetime.now(timezone.utc).date()
        result = await session.execute(
            select(Stop)
            .join(Trip, Stop.trip_id == Trip.id)
            .where(
                Stop.status == StopStatus.PUBLISHED,
                Trip.status == TripStatus.PUBLISHED,
                func.date(Stop.start_date) <= today,
                or_(Stop.end_date.is_(None), func.date(Stop.end_date) >= today),
            )
            .order_by(Stop.start_date.desc())
            .limit(1)
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

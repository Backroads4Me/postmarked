"""
Visibility and privacy service.

Implements the min(self, parent) visibility rule and provides helpers
for stripping private fields from public API responses.

Rule: a public photo on a private stop is private. Deny returns 404
(not 403) to avoid leaking existence to anonymous viewers.
"""
from __future__ import annotations

import uuid
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ApprovalState, MediaProcessingState, PostStatus, StopStatus, TripStatus, UserRole, Visibility


# Fields that must NEVER appear in public/anonymous responses
PRIVATE_STOP_FIELDS = {
    "reservation_private",
    "site_number_private",
    "private_note",
}

PRIVATE_PLANNED_STOP_FIELDS = {
    "reservation_private",
    "comments_private",
    "camping_cost",
    "meals_cost",
    "misc_cost",
    "fuel_cost",
    "stop_total_cost",
    "starting_fuel",
    "fuel_used",
    "arrival_fuel",
    "fuel_added",
    "departure_fuel",
    "phone",
    "email",
}


def is_admin(user) -> bool:
    if not user:
        return False
    role = getattr(user, "role", None)
    return getattr(role, "value", role) == UserRole.ADMIN.value


def effective_visibility(entity_visibility, parent_visibility) -> str:
    """
    min(entity, parent) where PRIVATE < PUBLIC.
    A public photo on a private stop is private.
    Accepts either Visibility enum or its string value.
    """
    def _val(v):
        return getattr(v, "value", v)

    if _val(parent_visibility) == Visibility.PRIVATE.value:
        return Visibility.PRIVATE.value
    return _val(entity_visibility)


def is_visible_to_user(entity_visibility, parent_visibility, user) -> bool:
    """Check if an entity is visible to a given user."""
    eff = effective_visibility(entity_visibility, parent_visibility)
    if eff == Visibility.PUBLIC.value:
        return True
    if not user:
        return False
    return True


def is_ready_media_visible_to_user(asset, user) -> bool:
    """Return true when a media asset is ready and visible to this reader."""
    if not asset:
        return False
    if asset.processing_state != MediaProcessingState.READY:
        return False
    return asset.visibility == Visibility.PUBLIC or bool(user)


def visible_ready_media(media, user) -> list:
    """Filter media lists for public serializers while hiding pending/failed assets."""
    return [asset for asset in media if is_ready_media_visible_to_user(asset, user)]


def visible_ready_cover_media(asset, user):
    """Return a ready visible cover asset, or None for serializers."""
    return asset if is_ready_media_visible_to_user(asset, user) else None


def strip_private_fields(data: dict, fields: set) -> dict:
    """Remove private fields from a response dict."""
    return {k: v for k, v in data.items() if k not in fields}


def extract_lat_lon(location) -> tuple[float | None, float | None]:
    """
    Extract lat/lon from a GeoAlchemy2 WKB element.
    Returns (latitude, longitude) or (None, None).
    """
    if location is None:
        return None, None
    try:
        from geoalchemy2.shape import to_shape
        point = to_shape(location)
        return point.y, point.x  # lat, lon
    except Exception:
        try:
            s = str(location)
            if "POINT" in s:
                coords = s.replace("POINT(", "").replace(")", "").strip().split()
                return float(coords[1]), float(coords[0])
        except Exception:
            pass
    return None, None


# ──────────────────────────────────────────────────────────────────────────
# Comment / Like target resolution
# ──────────────────────────────────────────────────────────────────────────

# Allowed values for Comment.target_kind / Like.target_kind
ALLOWED_TARGET_KINDS = {"stop", "media", "post"}


async def load_target_with_visibility(
    session: AsyncSession,
    target_kind: str,
    target_id: uuid.UUID,
) -> Optional[Tuple[object, str]]:
    """
    Load a Comment/Like target by (kind, id) and return (target, effective_visibility_value).
    Returns None if the target does not exist or is not published in its parent chain.
    """
    # Imported inside function to avoid circular import at module load
    from app.models.content import MediaAsset, Post, Stop, Trip

    if target_kind not in ALLOWED_TARGET_KINDS:
        return None

    if target_kind == "stop":
        result = await session.execute(
            select(Stop, Trip.visibility, Trip.status)
            .outerjoin(Trip, Stop.trip_id == Trip.id)
            .where(Stop.id == target_id)
        )
        row = result.first()
        if not row:
            return None
        stop, trip_vis, trip_status = row
        if stop.status != StopStatus.PUBLISHED or trip_status != TripStatus.PUBLISHED:
            return None
        return stop, effective_visibility(stop.visibility, trip_vis)

    if target_kind == "post":
        result = await session.execute(
            select(Post, Stop.visibility, Stop.status, Trip.visibility, Trip.status)
            .outerjoin(Stop, Post.stop_id == Stop.id)
            .outerjoin(Trip, (Post.trip_id == Trip.id) | (Stop.trip_id == Trip.id))
            .where(Post.id == target_id)
        )
        row = result.first()
        if not row:
            return None
        post, stop_vis, stop_status, trip_vis, trip_status = row
        if post.status != PostStatus.PUBLISHED:
            return None
        if stop_status is not None and stop_status != StopStatus.PUBLISHED:
            return None
        if trip_status is not None and trip_status != TripStatus.PUBLISHED:
            return None
        parent_vis = effective_visibility(stop_vis, trip_vis) if stop_vis is not None else trip_vis
        return post, effective_visibility(post.visibility, parent_vis)

    if target_kind == "media":
        media = await session.get(MediaAsset, target_id)
        if not media:
            return None
        # Resolve the parent — prefer post, then stop, then trip
        parent_vis = None
        parent_published = True
        if media.post_id:
            result = await session.execute(
                select(Post, Stop.visibility, Stop.status, Trip.visibility, Trip.status)
                .outerjoin(Stop, Post.stop_id == Stop.id)
                .outerjoin(Trip, (Post.trip_id == Trip.id) | (Stop.trip_id == Trip.id))
                .where(Post.id == media.post_id)
            )
            row = result.first()
            if row:
                post, stop_vis, stop_status, trip_vis, trip_status = row
                parent_published = post.status == PostStatus.PUBLISHED
                if stop_status is not None:
                    parent_published = parent_published and stop_status == StopStatus.PUBLISHED
                if trip_status is not None:
                    parent_published = parent_published and trip_status == TripStatus.PUBLISHED
                parent_vis = effective_visibility(
                    post.visibility,
                    effective_visibility(stop_vis, trip_vis) if stop_vis is not None else trip_vis,
                )
        if parent_vis is None and media.stop_id:
            result = await session.execute(
                select(Stop.visibility, Stop.status, Trip.visibility, Trip.status)
                .select_from(Stop)
                .outerjoin(Trip, Stop.trip_id == Trip.id)
                .where(Stop.id == media.stop_id)
            )
            row = result.first()
            if row:
                stop_vis, stop_status, trip_vis, trip_status = row
                parent_published = stop_status == StopStatus.PUBLISHED and trip_status == TripStatus.PUBLISHED
                parent_vis = effective_visibility(stop_vis, trip_vis)
        if parent_vis is None and media.trip_id:
            trip = await session.get(Trip, media.trip_id)
            if trip:
                parent_published = trip.status == TripStatus.PUBLISHED
                parent_vis = trip.visibility
        if not parent_published:
            return None
        return media, effective_visibility(media.visibility, parent_vis)

    return None

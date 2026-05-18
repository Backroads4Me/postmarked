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

from app.models.enums import ApprovalState, MediaProcessingState, UserRole, Visibility


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
    if is_admin(user):
        return True
    if getattr(user, "approval_state", None) == ApprovalState.APPROVED:
        # Approved users can see private content per design (family members).
        # Tighten further if you want only-admin-sees-private.
        return True
    return False


def is_ready_media_visible_to_user(asset, user) -> bool:
    """Return true when a media asset is ready and visible to this reader."""
    if not asset:
        return False
    if asset.processing_state != MediaProcessingState.READY:
        return False
    return is_admin(user) or asset.visibility == Visibility.PUBLIC


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
    Returns None if the target does not exist.
    """
    # Imported inside function to avoid circular import at module load
    from app.models.content import MediaAsset, Post, Stop, Trip

    if target_kind not in ALLOWED_TARGET_KINDS:
        return None

    if target_kind == "stop":
        result = await session.execute(
            select(Stop, Trip.visibility)
            .outerjoin(Trip, Stop.trip_id == Trip.id)
            .where(Stop.id == target_id)
        )
        row = result.first()
        if not row:
            return None
        stop, trip_vis = row
        return stop, trip_vis

    if target_kind == "post":
        result = await session.execute(
            select(Post, Trip.visibility)
            .outerjoin(Stop, Post.stop_id == Stop.id)
            .outerjoin(Trip, (Post.trip_id == Trip.id) | (Stop.trip_id == Trip.id))
            .where(Post.id == target_id)
        )
        row = result.first()
        if not row:
            return None
        post, trip_vis = row
        # Effective = min(post, stop_or_trip)
        return post, effective_visibility(post.visibility, trip_vis)

    if target_kind == "media":
        media = await session.get(MediaAsset, target_id)
        if not media:
            return None
        # Resolve the parent — prefer post, then stop, then trip
        parent_vis = None
        if media.post_id:
            post = await session.get(Post, media.post_id)
            if post:
                parent_vis = post.visibility
        if parent_vis is None and media.stop_id:
            result = await session.execute(
                select(Trip.visibility)
                .join(Stop, Stop.trip_id == Trip.id)
                .where(Stop.id == media.stop_id)
            )
            parent_vis = result.scalar_one_or_none()
        if parent_vis is None and media.trip_id:
            trip = await session.get(Trip, media.trip_id)
            if trip:
                parent_vis = trip.visibility
        return media, effective_visibility(media.visibility, parent_vis)

    return None

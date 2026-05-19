"""
Media streaming endpoint.

Spec §4.3: a single authenticated route serving original + derivative bytes
with Range/ETag support. Visibility is enforced as min(self, parent). Deny
returns 404 — never 403, never 401 — to avoid leaking the existence of
private assets.

Browsers sending the session cookie get authorized automatically (same-origin
fetch from <img> / <video>). Cross-origin embeds are not supported in V1.
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.auth_config import fastapi_users_app
from app.db import get_async_session
from app.models.content import MediaAsset, Post, Stop, Trip
from app.models.enums import MediaKind, PostStatus, StopStatus, TripStatus
from app.services.visibility import effective_visibility, is_visible_to_user

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/tmp/originals")
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/tmp/derivatives")

# Variants the worker actually produces today (api/app/tasks.py).
# Add more here as tasks.py grows.
PHOTO_VARIANTS = {"original", "webp"}
VIDEO_VARIANTS = {"original", "poster"}

router = APIRouter(prefix="/media", tags=["media"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)


def _resolve_path(asset: MediaAsset, variant: str) -> Optional[tuple[str, str]]:
    """
    Map (asset, variant) to (filesystem_path, mime_type) or None if unknown.
    """
    if variant == "original":
        return asset.original_path, asset.mime_type or "application/octet-stream"

    if variant == "webp":
        path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.webp")
        return path, "image/webp"

    if variant == "poster":
        path = os.path.join(DERIVATIVES_PATH, f"{asset.id}-poster.jpg")
        return path, "image/jpeg"

    return None


async def _parent_visibility(session: AsyncSession, asset: MediaAsset):
    """Return the strongest parent visibility and whether the parent chain is published."""
    if asset.post_id:
        result = await session.execute(
            select(Post, Stop.visibility, Stop.status, Trip.visibility, Trip.status)
            .outerjoin(Stop, Post.stop_id == Stop.id)
            .outerjoin(Trip, (Post.trip_id == Trip.id) | (Stop.trip_id == Trip.id))
            .where(Post.id == asset.post_id)
        )
        row = result.first()
        if row:
            post, stop_vis, stop_status, trip_vis, trip_status = row
            published = post.status == PostStatus.PUBLISHED
            if stop_status is not None:
                published = published and stop_status == StopStatus.PUBLISHED
            if trip_status is not None:
                published = published and trip_status == TripStatus.PUBLISHED
            parent_vis = effective_visibility(stop_vis, trip_vis) if stop_vis is not None else trip_vis
            return effective_visibility(post.visibility, parent_vis), published
    if asset.stop_id:
        result = await session.execute(
            select(Stop.visibility, Stop.status, Trip.visibility, Trip.status)
            .select_from(Stop)
            .outerjoin(Trip, Stop.trip_id == Trip.id)
            .where(Stop.id == asset.stop_id)
        )
        row = result.first()
        if row:
            stop_vis, stop_status, trip_vis, trip_status = row
            return effective_visibility(stop_vis, trip_vis), stop_status == StopStatus.PUBLISHED and trip_status == TripStatus.PUBLISHED
    if asset.trip_id:
        trip = await session.get(Trip, asset.trip_id)
        if trip:
            return trip.visibility, trip.status == TripStatus.PUBLISHED
    return None, True


def _range_response(path: str, mime_type: str, range_header: str, etag: str) -> Response:
    """Serve a byte range from disk. Standard `bytes=START-END` parsing."""
    file_size = os.path.getsize(path)

    try:
        units, _, ranges = range_header.partition("=")
        if units.strip().lower() != "bytes":
            raise ValueError("only byte ranges supported")
        start_s, _, end_s = ranges.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
    except (ValueError, IndexError):
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    if start > end or end >= file_size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    chunk_size = end - start + 1

    def iterfile():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                buf = f.read(min(64 * 1024, remaining))
                if not buf:
                    break
                remaining -= len(buf)
                yield buf

    return StreamingResponse(
        iterfile(),
        status_code=206,
        media_type=mime_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Cache-Control": "private, max-age=86400",
            "ETag": etag,
        },
    )


@router.get("/{asset_id}/{variant}")
async def get_media(
    asset_id: uuid.UUID,
    variant: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Not found")

    allowed = PHOTO_VARIANTS if asset.kind == MediaKind.PHOTO else VIDEO_VARIANTS
    if variant not in allowed:
        raise HTTPException(status_code=404, detail="Not found")

    parent_vis, parent_published = await _parent_visibility(session, asset)
    if not parent_published and not user:
        raise HTTPException(status_code=404, detail="Not found")
    eff_vis = effective_visibility(asset.visibility, parent_vis)
    if not is_visible_to_user(eff_vis, None, user):
        # Deny == 404, not 403, per spec.
        raise HTTPException(status_code=404, detail="Not found")

    resolved = _resolve_path(asset, variant)
    if not resolved:
        raise HTTPException(status_code=404, detail="Not found")

    path, mime_type = resolved
    if not os.path.exists(path):
        # Asset row exists but bytes are missing (worker still pending, or lost file).
        raise HTTPException(status_code=404, detail="Not found")

    # ETag = sha256 (already computed at upload). Falls back to mtime+size if missing.
    if asset.original_sha256:
        etag = f'"sha256-{asset.original_sha256[:16]}-{variant}"'
    else:
        stat = os.stat(path)
        etag = f'"{int(stat.st_mtime)}-{stat.st_size}-{variant}"'

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    range_header = request.headers.get("range")
    if range_header:
        return _range_response(path, mime_type, range_header, etag)

    return FileResponse(
        path,
        media_type=mime_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "ETag": etag,
            "Accept-Ranges": "bytes",
        },
    )

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
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
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
PHOTO_VARIANTS = {"original", "webp", "avif", "webp_sm"}
VIDEO_VARIANTS = {"original", "poster", "mp4"}

# Regex matching a hashed derivative filename: {variant}-{hash8}.{ext}
_HASHED_FILENAME_RE = re.compile(r"^[a-z_]+-[0-9a-f]{8,}\.\w+$")

router = APIRouter(prefix="/media", tags=["media"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)


def _resolve_legacy_path(asset: MediaAsset, variant: str) -> Optional[tuple[str, str]]:
    """
    Map (asset, legacy variant name) to (filesystem_path, mime_type) or None.
    Used only for the legacy fallback when derivative_paths has no hashed entry.
    """
    if variant == "original":
        return asset.original_path, asset.mime_type or "application/octet-stream"

    if variant == "webp":
        path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.webp")
        return path, "image/webp"

    if variant == "avif":
        path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.avif")
        return path, "image/avif"

    if variant == "webp_sm":
        path = os.path.join(DERIVATIVES_PATH, f"{asset.id}_sm.webp")
        return path, "image/webp"

    if variant == "mp4":
        path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.mp4")
        return path, "video/mp4"

    if variant == "poster":
        path = os.path.join(DERIVATIVES_PATH, f"{asset.id}-poster.jpg")
        return path, "image/jpeg"

    return None


def _resolve_hashed_path(asset: MediaAsset, filename: str) -> Optional[tuple[str, str]]:
    """
    Map a hashed derivative filename to (filesystem_path, mime_type) or None.
    Only accepts filenames that exactly match a value in derivative_paths.
    """
    dp = asset.derivative_paths or {}
    # Check that this filename is in the asset's derivative_paths values
    matched = False
    for url_path in dp.values():
        # url_path looks like /media/{asset_id}/{filename}
        if url_path.endswith("/" + filename):
            matched = True
            break
    if not matched:
        return None

    # Derive filesystem path — on disk: {DERIVATIVES_PATH}/{asset_id}-{filename}
    disk_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}-{filename}")

    # Determine MIME type from extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "mp4": "video/mp4",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "avif": "image/avif",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")
    return disk_path, mime_type


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


def _range_response(path: str, mime_type: str, range_header: str, etag: str, cache_control: str) -> Response:
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
            "Cache-Control": cache_control,
            "ETag": etag,
        },
    )


def _file_etag(path: str, variant: str) -> str:
    stat = os.stat(path)
    mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
    return f'"file-{mtime_ns:x}-{stat.st_size:x}-{variant}"'


def _cache_control_immutable() -> str:
    """Cache headers for hashed (immutable) derivatives."""
    return "public, max-age=31536000, immutable, no-transform"


def _cache_control_legacy(variant: str, is_public: bool) -> str:
    """Cache headers for legacy (unhashed) derivative routes."""
    if not is_public:
        return "private, max-age=86400"
    # Short cache for all legacy routes — they'll 301 once backfilled.
    return "public, max-age=3600, must-revalidate, no-transform"


async def _check_asset_access(
    asset_id: uuid.UUID,
    session: AsyncSession,
    user,
) -> tuple[MediaAsset, str, bool]:
    """Load asset and verify visibility. Returns (asset, eff_vis, parent_published).
    Raises HTTPException(404) on denial."""
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Not found")

    parent_vis, parent_published = await _parent_visibility(session, asset)
    if not parent_published and not user:
        raise HTTPException(status_code=404, detail="Not found")
    eff_vis = effective_visibility(asset.visibility, parent_vis)
    if not is_visible_to_user(eff_vis, None, user):
        # Deny == 404, not 403, per spec.
        raise HTTPException(status_code=404, detail="Not found")

    return asset, eff_vis, parent_published


def _serve_file(
    path: str,
    mime_type: str,
    variant: str,
    cache_control: str,
    request: Request,
    head_only: bool,
) -> Response:
    """Common file serving logic with ETag, Range, and HEAD support."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")

    etag = _file_etag(path, variant)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    range_header = request.headers.get("range")
    if range_header:
        if head_only:
            file_size = os.path.getsize(path)
            try:
                units, _, ranges = range_header.partition("=")
                if units.strip().lower() != "bytes":
                    raise ValueError
                start_s, _, end_s = ranges.partition("-")
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else file_size - 1
                if start > end or end >= file_size:
                    return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
            except (ValueError, IndexError):
                return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
            return Response(
                status_code=206,
                media_type=mime_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(end - start + 1),
                    "Cache-Control": cache_control,
                    "ETag": etag,
                },
            )
        return _range_response(path, mime_type, range_header, etag, cache_control)

    if head_only:
        stat = os.stat(path)
        return Response(
            status_code=200,
            media_type=mime_type,
            headers={
                "Cache-Control": cache_control,
                "ETag": etag,
                "Accept-Ranges": "bytes",
                "Content-Length": str(stat.st_size),
            },
        )

    return FileResponse(
        path,
        media_type=mime_type,
        headers={
            "Cache-Control": cache_control,
            "ETag": etag,
            "Accept-Ranges": "bytes",
        },
    )


def _is_hashed_filename(filename: str) -> bool:
    """Check if a filename matches the immutable pattern: {variant}-{hash8}.{ext}"""
    return bool(_HASHED_FILENAME_RE.match(filename))


def _find_hashed_url(asset: MediaAsset, variant: str) -> Optional[str]:
    """
    Check if derivative_paths has a hashed URL for the given legacy variant name.
    Returns the hashed URL path (e.g. /media/{id}/mp4-a1b2c3d4.mp4) or None.
    """
    dp = asset.derivative_paths or {}
    url_path = dp.get(variant)
    if not url_path:
        return None
    # Check if it's a hashed URL (contains a hash pattern) vs old-style /media/{id}/mp4
    # Old-style: /media/{id}/{variant}   (no dot, no hash)
    # Hashed:    /media/{id}/{variant}-{hash8}.{ext}
    parts = url_path.rsplit("/", 1)
    if len(parts) == 2 and _is_hashed_filename(parts[1]):
        return url_path
    return None


async def _legacy_media_response(
    asset_id: uuid.UUID,
    variant: str,
    request: Request,
    head_only: bool,
    session: AsyncSession,
    user,
):
    """Handle legacy variant routes like /media/{id}/mp4, /media/{id}/poster, etc."""
    asset, eff_vis, parent_published = await _check_asset_access(asset_id, session, user)

    allowed = PHOTO_VARIANTS if asset.kind == MediaKind.PHOTO else VIDEO_VARIANTS
    if variant not in allowed:
        raise HTTPException(status_code=404, detail="Not found")

    # If derivative_paths has a hashed URL for this variant, 301 redirect
    hashed_url = _find_hashed_url(asset, variant)
    if hashed_url:
        return RedirectResponse(url=hashed_url, status_code=301)

    resolved = _resolve_legacy_path(asset, variant)
    if not resolved:
        raise HTTPException(status_code=404, detail="Not found")

    path, mime_type = resolved
    is_public = eff_vis == "public" and parent_published
    cache_control = _cache_control_legacy(variant, is_public)
    return _serve_file(path, mime_type, variant, cache_control, request, head_only)


async def _hashed_media_response(
    asset_id: uuid.UUID,
    filename: str,
    request: Request,
    head_only: bool,
    session: AsyncSession,
    user,
):
    """Handle hashed derivative routes like /media/{id}/mp4-a1b2c3d4.mp4."""
    asset, eff_vis, parent_published = await _check_asset_access(asset_id, session, user)

    resolved = _resolve_hashed_path(asset, filename)
    if not resolved:
        raise HTTPException(status_code=404, detail="Not found")

    path, mime_type = resolved
    variant = filename.rsplit("-", 1)[0] if "-" in filename else filename
    is_public = eff_vis == "public" and parent_published
    cache_control = _cache_control_immutable() if is_public else "private, max-age=86400"
    return _serve_file(path, mime_type, variant, cache_control, request, head_only)


async def _media_response(
    asset_id: uuid.UUID,
    variant: str,
    request: Request,
    head_only: bool,
    session: AsyncSession,
    user,
):
    """Unified dispatcher: routes hashed filenames to immutable handler, legacy names to legacy handler."""
    if _is_hashed_filename(variant):
        return await _hashed_media_response(asset_id, variant, request, head_only, session, user)
    else:
        return await _legacy_media_response(asset_id, variant, request, head_only, session, user)


@router.get("/{asset_id}/{variant}")
async def get_media(
    asset_id: uuid.UUID,
    variant: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    return await _media_response(asset_id, variant, request, False, session, user)


@router.head("/{asset_id}/{variant}")
async def head_media(
    asset_id: uuid.UUID,
    variant: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    return await _media_response(asset_id, variant, request, True, session, user)

import os
import uuid
import json
import base64
import hashlib
from fastapi import APIRouter, Depends, Query, Request, Response, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from pydantic import BaseModel
from datetime import date as date_type
from sqlalchemy import cast, func, select, Date
from sqlalchemy.exc import IntegrityError

from app.db import get_async_session
from app.auth.dependencies import current_admin_user
from app.models.content import MediaAsset, Stop, Trip
from app.models.enums import MediaKind, MediaProcessingState, Visibility
from app.tasks import process_media_asset
from app.schemas.media import MediaAssetOut
from app.services.media_storage import delete_media_asset_files
from app.services.visibility import child_visibility_for_parent

router = APIRouter(prefix="/media", tags=["admin-media"])  # tus sub-router lives at /media/tus

ADMIN_TZ = os.getenv("PUBLIC_ADMIN_TIMEZONE", "UTC")


def _asset_date_expr():
    """Cast created_at to DATE in the configured admin timezone."""
    return cast(func.timezone(ADMIN_TZ, MediaAsset.created_at), Date)


def _unassigned_media_filter():
    return (
        MediaAsset.stop_id.is_(None),
        MediaAsset.post_id.is_(None),
        MediaAsset.trip_id.is_(None),
    )


@router.get("", response_model=List[MediaAssetOut])
async def list_media_admin(
    date: Optional[date_type] = Query(None),
    unassigned: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    q = select(MediaAsset).order_by(MediaAsset.created_at.desc())
    if date is not None:
        q = q.where(_asset_date_expr() == date)
    if unassigned:
        q = q.where(*_unassigned_media_filter())
    result = await session.execute(q)
    return result.scalars().all()


@router.get("/dates", response_model=List[str])
async def list_media_dates_admin(
    unassigned: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    date_expr = _asset_date_expr()
    q = select(date_expr).distinct().order_by(date_expr.desc())
    if unassigned:
        q = q.where(*_unassigned_media_filter())
    result = await session.execute(q)
    return [row.isoformat() for row in result.scalars().all()]


@router.get("/orphans", response_model=List[MediaAssetOut])
async def list_media_orphans_admin(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    query = (
        select(MediaAsset)
        .where(MediaAsset.stop_id.is_(None))
        .order_by(MediaAsset.created_at.desc())
    )
    result = await session.execute(query)
    return result.scalars().all()


class AssignMediaRequest(BaseModel):
    media_ids: List[uuid.UUID]
    stop_id: uuid.UUID
    visibility: Optional[Visibility] = None  # explicit override; default = inherit from trip


class UpdateMediaRequest(BaseModel):
    caption: Optional[str] = None
    alt_text: Optional[str] = None


@router.post("/assign", response_model=dict)
async def assign_media_admin(
    req: AssignMediaRequest,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    stop = await session.get(Stop, req.stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    trip = await session.get(Trip, stop.trip_id)
    parent_visibility = trip.visibility if trip else Visibility.PRIVATE
    inherited = child_visibility_for_parent(parent_visibility, req.visibility)

    assigned = 0
    for mid in req.media_ids:
        asset = await session.get(MediaAsset, mid)
        if not asset:
            continue
        asset.stop_id = req.stop_id
        # Inherit from parent trip unless an explicit visibility override was passed.
        # Effective visibility at read time is still min(self, parent), enforced by
        # the streaming endpoint and visibility service.
        asset.visibility = inherited
        assigned += 1

    await session.commit()
    return {"status": "assigned", "count": assigned, "visibility": inherited.value}


# ──────────────────────────────────────────────────────────────────────────
# TUS resumable upload
# ──────────────────────────────────────────────────────────────────────────

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/tmp/originals")
os.makedirs(ORIGINALS_PATH, exist_ok=True)

TUS_VERSION = "1.0.0"
DEFAULT_MAX_UPLOAD_BYTES = 250 * 1024 * 1024
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES)))
ALLOWED_UPLOAD_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "video/mp4",
    "video/quicktime",
}


def get_metadata(req: Request) -> dict:
    meta_raw = req.headers.get("Upload-Metadata", "")
    metadata = {}
    if meta_raw:
        for pair in meta_raw.split(","):
            parts = pair.strip().split(" ")
            if len(parts) == 2:
                try:
                    metadata[parts[0]] = base64.b64decode(parts[1]).decode("utf-8")
                except Exception:
                    pass
    return metadata


@router.options("/tus")
@router.options("/tus/{file_id}")
async def options_tus():
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={
            "Tus-Resumable": TUS_VERSION,
            "Tus-Version": TUS_VERSION,
            "Tus-Extension": "creation",
            "Access-Control-Expose-Headers": (
                "Tus-Resumable, Tus-Version, Tus-Extension, "
                "Upload-Offset, Upload-Length, Location"
            ),
        },
    )


@router.post("/tus")
async def create_upload(
    request: Request,
    upload_length: int = Header(None, alias="Upload-Length"),
    user=Depends(current_admin_user),
):
    if upload_length is None:
        raise HTTPException(status_code=400, detail="Upload-Length required")
    if upload_length < 1:
        raise HTTPException(status_code=400, detail="Upload-Length must be positive")
    if upload_length > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload too large")

    file_id = str(uuid.uuid4())
    metadata = get_metadata(request)
    mime = metadata.get("filetype", "application/octet-stream").lower()
    if mime not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {mime}")

    state = {
        "upload_length": upload_length,
        "offset": 0,
        "metadata": metadata,
    }
    with open(os.path.join(ORIGINALS_PATH, f"{file_id}.json"), "w") as f:
        json.dump(state, f)
    open(os.path.join(ORIGINALS_PATH, f"{file_id}.bin"), "wb").close()

    headers = {
        "Tus-Resumable": TUS_VERSION,
        "Location": f"/api/admin/media/tus/{file_id}",
        "Upload-Offset": "0",
        "Access-Control-Expose-Headers": "Tus-Resumable, Location, Upload-Offset",
    }
    return Response(status_code=status.HTTP_201_CREATED, headers=headers)


@router.head("/tus/{file_id}")
async def head_upload(file_id: uuid.UUID, user=Depends(current_admin_user)):
    info_path = os.path.join(ORIGINALS_PATH, f"{file_id}.json")
    if not os.path.exists(info_path):
        raise HTTPException(status_code=404, detail="Upload not found")

    with open(info_path, "r") as f:
        state = json.load(f)

    return Response(
        status_code=status.HTTP_200_OK,
        headers={
            "Tus-Resumable": TUS_VERSION,
            "Upload-Offset": str(state["offset"]),
            "Upload-Length": str(state["upload_length"]),
            "Cache-Control": "no-store",
            "Access-Control-Expose-Headers": "Tus-Resumable, Upload-Offset, Upload-Length",
        },
    )


def _cleanup_temp(file_id: str) -> None:
    for ext in ("bin", "json"):
        p = os.path.join(ORIGINALS_PATH, f"{file_id}.{ext}")
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


@router.patch("/tus/{file_id}")
async def patch_upload(
    file_id: uuid.UUID,
    request: Request,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    content_type: str = Header(..., alias="Content-Type"),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    if content_type != "application/offset+octet-stream":
        raise HTTPException(status_code=415, detail="Unsupported Content-Type")

    info_path = os.path.join(ORIGINALS_PATH, f"{file_id}.json")
    bin_path = os.path.join(ORIGINALS_PATH, f"{file_id}.bin")

    if not os.path.exists(info_path):
        raise HTTPException(status_code=404, detail="Upload not found")

    with open(info_path, "r") as f:
        state = json.load(f)

    if state["offset"] != upload_offset:
        raise HTTPException(status_code=409, detail="Conflict in offset")

    with open(bin_path, "ab") as f:
        async for chunk in request.stream():
            if state["offset"] + len(chunk) > state["upload_length"]:
                raise HTTPException(status_code=413, detail="Upload exceeds declared length")
            f.write(chunk)
            state["offset"] += len(chunk)

    with open(info_path, "w") as f:
        json.dump(state, f)

    response_headers = {
        "Tus-Resumable": TUS_VERSION,
        "Upload-Offset": str(state["offset"]),
    }

    if state["offset"] >= state["upload_length"]:
        # T-007: dedup on SHA-256 before insert. If the file is already known,
        # discard the freshly uploaded bytes and return the existing asset id.
        with open(bin_path, "rb") as uploaded:
            digest = hashlib.sha256()
            for chunk in iter(lambda: uploaded.read(64 * 1024), b""):
                digest.update(chunk)
            original_sha256 = digest.hexdigest()

        existing_q = select(MediaAsset).where(MediaAsset.original_sha256 == original_sha256)
        existing = (await session.execute(existing_q)).scalar_one_or_none()
        if existing:
            _cleanup_temp(str(file_id))
            response_headers["X-Postmarked-Asset-Id"] = str(existing.id)
            response_headers["X-Postmarked-Duplicate-Of"] = str(existing.id)
            response_headers["Access-Control-Expose-Headers"] = (
                "Tus-Resumable, Upload-Offset, X-Postmarked-Asset-Id, X-Postmarked-Duplicate-Of"
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response_headers)

        mime = state["metadata"].get("filetype", "application/octet-stream")
        filename = state["metadata"].get("filename", f"{file_id}.bin")
        kind = MediaKind.VIDEO if "video" in mime else MediaKind.PHOTO

        asset = MediaAsset(
            id=file_id,
            kind=kind,
            original_path=bin_path,
            original_sha256=original_sha256,
            original_filename=filename,
            original_size_bytes=os.path.getsize(bin_path),
            mime_type=mime,
            processing_state=MediaProcessingState.PENDING,
            # Default to PRIVATE on upload; admin assigns to a stop later which
            # inherits the stop's visibility. Never default to PUBLIC.
            visibility=Visibility.PRIVATE,
            featured=False,
            sort_order=1,
        )
        session.add(asset)
        try:
            await session.commit()
        except IntegrityError:
            # Race-condition fallback: another upload completed first with same SHA.
            await session.rollback()
            existing = (await session.execute(existing_q)).scalar_one_or_none()
            if existing:
                _cleanup_temp(str(file_id))
                response_headers["X-Postmarked-Asset-Id"] = str(existing.id)
                response_headers["X-Postmarked-Duplicate-Of"] = str(existing.id)
                response_headers["Access-Control-Expose-Headers"] = (
                    "Tus-Resumable, Upload-Offset, X-Postmarked-Asset-Id, X-Postmarked-Duplicate-Of"
                )
                return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response_headers)
            raise

        process_media_asset.delay(str(file_id))
        response_headers["X-Postmarked-Asset-Id"] = str(asset.id)
        response_headers["Access-Control-Expose-Headers"] = (
            "Tus-Resumable, Upload-Offset, X-Postmarked-Asset-Id"
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response_headers)


@router.get("/{asset_id}", response_model=MediaAssetOut)
async def get_media_asset_admin(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.patch("/{asset_id}", response_model=MediaAssetOut)
async def update_media_asset(
    asset_id: uuid.UUID,
    req: UpdateMediaRequest,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    update_data = req.model_dump(exclude_unset=True)
    if "caption" in update_data:
        asset.caption = (update_data["caption"] or "").strip() or None
    if "alt_text" in update_data:
        asset.alt_text = (update_data["alt_text"] or "").strip() or None

    await session.commit()
    await session.refresh(asset)
    return asset


@router.post("/{asset_id}/detach")
async def detach_media_asset(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.stop_id = None
    asset.post_id = None
    asset.trip_id = None
    asset.visibility = Visibility.PRIVATE
    await session.commit()
    return {"ok": True}


@router.post("/{asset_id}/requeue")
async def requeue_media_asset(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.processing_state = MediaProcessingState.PENDING
    await session.commit()
    process_media_asset.delay(str(asset_id))
    return {"ok": True}


@router.delete("/{asset_id}")
async def delete_media_asset(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    await session.delete(asset)
    await session.commit()
    delete_media_asset_files(asset)
    return {"ok": True}

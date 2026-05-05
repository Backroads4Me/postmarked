import os
import uuid
import json
import base64
import hashlib
from fastapi import APIRouter, Depends, Request, Response, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import get_async_session
from app.auth.dependencies import current_admin_user
from app.models.content import MediaAsset, Stop
from app.models.enums import MediaKind, MediaProcessingState, Visibility
from app.tasks import process_media_asset
from app.schemas.media import MediaAssetOut

router = APIRouter(prefix="/media", tags=["admin-media"])  # tus sub-router lives at /media/tus


@router.get("", response_model=List[MediaAssetOut])
async def list_media_admin(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    result = await session.execute(select(MediaAsset).order_by(MediaAsset.created_at.desc()))
    return result.scalars().all()


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
    visibility: Optional[Visibility] = None  # explicit override; default = inherit from stop


@router.post("/assign", response_model=dict)
async def assign_media_admin(
    req: AssignMediaRequest,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user),
):
    stop = await session.get(Stop, req.stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    inherited = req.visibility if req.visibility is not None else stop.visibility

    assigned = 0
    for mid in req.media_ids:
        asset = await session.get(MediaAsset, mid)
        if not asset:
            continue
        asset.stop_id = req.stop_id
        # Inherit from parent stop unless an explicit visibility override was passed.
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

    file_id = str(uuid.uuid4())
    metadata = get_metadata(request)

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
async def head_upload(file_id: str, user=Depends(current_admin_user)):
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
    file_id: str,
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
            _cleanup_temp(file_id)
            response_headers["X-Goodpath-Asset-Id"] = str(existing.id)
            response_headers["X-Goodpath-Duplicate-Of"] = str(existing.id)
            response_headers["Access-Control-Expose-Headers"] = (
                "Tus-Resumable, Upload-Offset, X-Goodpath-Asset-Id, X-Goodpath-Duplicate-Of"
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response_headers)

        mime = state["metadata"].get("filetype", "application/octet-stream")
        filename = state["metadata"].get("filename", f"{file_id}.bin")
        kind = MediaKind.VIDEO if "video" in mime else MediaKind.PHOTO

        asset = MediaAsset(
            id=uuid.UUID(file_id),
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
                _cleanup_temp(file_id)
                response_headers["X-Goodpath-Asset-Id"] = str(existing.id)
                response_headers["X-Goodpath-Duplicate-Of"] = str(existing.id)
                response_headers["Access-Control-Expose-Headers"] = (
                    "Tus-Resumable, Upload-Offset, X-Goodpath-Asset-Id, X-Goodpath-Duplicate-Of"
                )
                return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response_headers)
            raise

        process_media_asset.delay(file_id)
        response_headers["X-Goodpath-Asset-Id"] = str(asset.id)
        response_headers["Access-Control-Expose-Headers"] = (
            "Tus-Resumable, Upload-Offset, X-Goodpath-Asset-Id"
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response_headers)

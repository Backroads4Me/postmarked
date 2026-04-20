import os
import uuid
import json
import base64
from fastapi import APIRouter, Depends, Request, Response, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from typing import List

from app.db import get_async_session
from sqlalchemy import select
from app.auth.dependencies import current_admin_user
from app.models.content import MediaAsset
from app.models.enums import MediaKind, MediaProcessingState, Visibility
from app.tasks import process_media_asset
from app.schemas.media import MediaAssetOut
from pydantic import BaseModel

router = APIRouter(prefix="/media", tags=["admin-media"]) # Keep root as /media, tus sub-router is /media/tus

@router.get("", response_model=List[MediaAssetOut])
async def list_media_admin(
    session: AsyncSession = Depends(get_async_session),
    user = Depends(current_admin_user)
):
    result = await session.execute(select(MediaAsset).order_by(MediaAsset.created_at.desc()))
    return result.scalars().all()

@router.get("/orphans", response_model=List[MediaAssetOut])
async def list_media_orphans_admin(
    session: AsyncSession = Depends(get_async_session),
    user = Depends(current_admin_user)
):
    query = select(MediaAsset).where(MediaAsset.stop_id == None).order_by(MediaAsset.created_at.desc())
    result = await session.execute(query)
    return result.scalars().all()

class AssignMediaRequest(BaseModel):
    media_ids: List[uuid.UUID]
    stop_id: uuid.UUID

@router.post("/assign", response_model=dict)
async def assign_media_admin(
    req: AssignMediaRequest,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(current_admin_user)
):
    for mid in req.media_ids:
        asset = await session.get(MediaAsset, mid)
        if asset:
            asset.stop_id = req.stop_id
            asset.visibility = Visibility.PUBLIC # Usually inherit from stop, simplify to public
    await session.commit()
    return {"status": "assigned", "count": len(req.media_ids)}

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
            "Access-Control-Expose-Headers": "Tus-Resumable, Tus-Version, Tus-Extension, Upload-Offset, Upload-Length, Location",
        }
    )

@router.post("/tus")
async def create_upload(
    request: Request, 
    upload_length: int = Header(None, alias="Upload-Length"),
    user=Depends(current_admin_user)
):
    if upload_length is None:
        raise HTTPException(status_code=400, detail="Upload-Length required")
    
    file_id = str(uuid.uuid4())
    metadata = get_metadata(request)
    
    # Store metadata state in JSON temporarily alongside bin
    state = {
        "upload_length": upload_length,
        "offset": 0,
        "metadata": metadata
    }
    with open(os.path.join(ORIGINALS_PATH, f"{file_id}.json"), "w") as f:
        json.dump(state, f)
    
    open(os.path.join(ORIGINALS_PATH, f"{file_id}.bin"), "wb").close()

    headers = {
        "Tus-Resumable": TUS_VERSION,
        "Location": f"/api/admin/media/tus/{file_id}",
        "Upload-Offset": "0",
        "Access-Control-Expose-Headers": "Tus-Resumable, Location, Upload-Offset"
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
            "Access-Control-Expose-Headers": "Tus-Resumable, Upload-Offset, Upload-Length"
        }
    )

@router.patch("/tus/{file_id}")
async def patch_upload(
    file_id: str,
    request: Request,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    content_type: str = Header(..., alias="Content-Type"),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_admin_user)
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
        
    # Write stream
    with open(bin_path, "ab") as f:
        async for chunk in request.stream():
            f.write(chunk)
            state["offset"] += len(chunk)
            
    with open(info_path, "w") as f:
        json.dump(state, f)

    if state["offset"] >= state["upload_length"]:
        # TUS Finish: Write DB row and enqueue celery!
        mime = state["metadata"].get("filetype", "application/octet-stream")
        kind = MediaKind.VIDEO if "video" in mime else MediaKind.IMAGE
        
        asset = MediaAsset(
            id=uuid.UUID(file_id),
            kind=kind,
            processing_state=MediaProcessingState.PENDING,
            visibility=Visibility.PUBLIC,
            featured=False, 
            sort_order=1
        )
        session.add(asset)
        await session.commit()
        
        # Dispatch Celery
        process_media_asset.delay(file_id)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={
            "Tus-Resumable": TUS_VERSION,
            "Upload-Offset": str(state["offset"])
        }
    )

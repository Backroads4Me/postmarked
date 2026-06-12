import logging
import os
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import MediaAsset
from app.models.enums import MediaKind, MediaProcessingState
from app.services.media_storage import DERIVATIVES_PATH, ORIGINALS_PATH

logger = logging.getLogger(__name__)
_HASHED_FILENAME_RE = re.compile(r"^[a-z_]+-[0-9a-f]{8,}\.\w+$")


def media_keep_originals() -> bool:
    return os.getenv("MEDIA_KEEP_ORIGINALS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def original_file_path(asset: MediaAsset) -> str:
    return asset.original_path or os.path.join(ORIGINALS_PATH, f"{asset.id}.bin")


def original_sidecar_path(asset: MediaAsset) -> str:
    return os.path.join(ORIGINALS_PATH, f"{asset.id}.json")


def delete_original_files(asset: MediaAsset) -> bool:
    deleted = False
    for path in (original_file_path(asset), original_sidecar_path(asset)):
        if path and os.path.exists(path):
            os.remove(path)
            deleted = True
    return deleted


def _derivative_path(asset: MediaAsset, variant: str) -> str | None:
    url_path = (asset.derivative_paths or {}).get(variant)
    if url_path:
        filename = url_path.rsplit("/", 1)[-1]
        if _HASHED_FILENAME_RE.match(filename):
            return os.path.join(DERIVATIVES_PATH, f"{asset.id}-{filename}")

    legacy_map = {
        "webp": f"{asset.id}.webp",
        "avif": f"{asset.id}.avif",
        "webp_sm": f"{asset.id}_sm.webp",
        "mp4": f"{asset.id}.mp4",
        "poster": f"{asset.id}-poster.jpg",
    }
    legacy_filename = legacy_map.get(variant)
    if legacy_filename:
        return os.path.join(DERIVATIVES_PATH, legacy_filename)
    return None


def _required_derivatives_exist(asset: MediaAsset) -> bool:
    if asset.kind == MediaKind.PHOTO:
        required = ("webp",)
    elif asset.kind == MediaKind.VIDEO:
        required = ("mp4", "poster")
    else:
        return False

    for variant in required:
        path = _derivative_path(asset, variant)
        if not path or not os.path.exists(path):
            return False
    return True


def delete_original_after_success(asset: MediaAsset) -> bool:
    if media_keep_originals() or asset.processing_state != MediaProcessingState.READY:
        return False
    if not _required_derivatives_exist(asset):
        logger.warning(
            "Keeping original for media asset %s because required derivatives are missing",
            asset.id,
        )
        return False
    deleted = delete_original_files(asset)
    if deleted:
        logger.info("Deleted original media for asset %s after successful processing", asset.id)
    return deleted


async def cleanup_processed_originals(session: AsyncSession) -> int:
    if media_keep_originals():
        logger.info("MEDIA_KEEP_ORIGINALS=true; skipping processed original cleanup")
        return 0

    result = await session.execute(
        select(MediaAsset).where(MediaAsset.processing_state == MediaProcessingState.READY)
    )
    deleted_count = 0
    for asset in result.scalars():
        if delete_original_after_success(asset):
            deleted_count += 1

    if deleted_count:
        logger.info("Deleted originals for %d previously processed media asset(s)", deleted_count)
    return deleted_count

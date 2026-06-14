import os
import re

from app.models.content import MediaAsset

MEDIA_DIR = os.getenv("MEDIA_DIR", "/media")
ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", os.path.join(MEDIA_DIR, "originals"))
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", os.path.join(MEDIA_DIR, "derivatives"))

_HASHED_FILENAME_RE = re.compile(r"^[a-z0-9_]+-[0-9a-f]{8,}\.\w+$")


def media_asset_file_paths(asset: MediaAsset) -> list[str]:
    """Return all filesystem paths associated with a media asset.

    Reads derivative_paths to resolve both hashed and legacy derivative
    filenames, and includes the original file and its sidecar JSON.
    """
    paths = []
    if asset.original_path:
        paths.append(asset.original_path)
    paths.append(os.path.join(ORIGINALS_PATH, f"{asset.id}.bin"))
    paths.append(os.path.join(ORIGINALS_PATH, f"{asset.id}.json"))

    dp = asset.derivative_paths or {}
    for variant, url_path in dp.items():
        if not url_path:
            continue
        parts = url_path.rsplit("/", 1)
        if len(parts) != 2:
            continue
        filename = parts[1]
        if _HASHED_FILENAME_RE.match(filename):
            paths.append(os.path.join(DERIVATIVES_PATH, f"{asset.id}-{filename}"))
        else:
            # Legacy filenames
            legacy_map = {
                "webp": f"{asset.id}.webp",
                "avif": f"{asset.id}.avif",
                "webp_sm": f"{asset.id}_sm.webp",
                "mp4": f"{asset.id}.mp4",
                "poster": f"{asset.id}-poster.jpg",
            }
            disk_filename = legacy_map.get(variant, filename)
            paths.append(os.path.join(DERIVATIVES_PATH, disk_filename))

    # Also include any legacy-named files that might still exist on disk
    # even if derivative_paths doesn't reference them (safety net during rollout)
    for suffix in (".webp", ".avif", "_sm.webp", ".mp4", "-poster.jpg"):
        paths.append(os.path.join(DERIVATIVES_PATH, f"{asset.id}{suffix}"))

    return list(dict.fromkeys(paths))


def delete_media_asset_files(asset: MediaAsset) -> None:
    for path in media_asset_file_paths(asset):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

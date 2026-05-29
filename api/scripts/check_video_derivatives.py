"""
Report video assets whose MP4 or poster derivative is missing or invalid.
After backfill, also validates that derivative_paths URLs are hashed (immutable).

Run from the api container:

    python /app/scripts/check_video_derivatives.py
"""

import os
import re
import subprocess

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.content import MediaAsset
from app.models.enums import MediaKind

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/postmarked",
).replace("postgresql://", "postgresql+psycopg://", 1)

DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/derivatives")

_HASHED_RE = re.compile(r"^[a-z_]+-[0-9a-f]{8,}\.\w+$")


def _is_hashed_url(url: str) -> bool:
    """Check if a derivative_paths URL is a hashed (immutable) URL."""
    parts = url.rsplit("/", 1)
    return len(parts) == 2 and bool(_HASHED_RE.match(parts[1]))


def _disk_path_for_url(asset_id: str, url: str) -> str | None:
    """Resolve a derivative_paths URL to a filesystem path."""
    parts = url.rsplit("/", 1)
    if len(parts) != 2:
        return None
    filename = parts[1]
    if _HASHED_RE.match(filename):
        return os.path.join(DERIVATIVES_PATH, f"{asset_id}-{filename}")
    # Legacy filenames
    legacy_map = {
        "mp4": f"{asset_id}.mp4",
        "poster": f"{asset_id}-poster.jpg",
    }
    return os.path.join(DERIVATIVES_PATH, legacy_map.get(filename, filename))


def is_valid_mp4(path: str) -> bool:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == "h264"
    except subprocess.CalledProcessError:
        return False


def main() -> None:
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        assets = db.execute(
            select(MediaAsset).where(MediaAsset.kind == MediaKind.VIDEO)
        ).scalars().all()

        print(f"Found {len(assets)} video asset(s).")
        missing_file = 0
        missing_metadata = 0
        invalid_file = 0
        missing_poster = 0
        old_style_mp4 = 0
        old_style_poster = 0

        for asset in assets:
            dp = asset.derivative_paths or {}
            mp4_url = dp.get("mp4", "")
            poster_url = dp.get("poster", "")

            has_mp4_metadata = bool(mp4_url)
            mp4_is_hashed = _is_hashed_url(mp4_url) if mp4_url else False
            poster_is_hashed = _is_hashed_url(poster_url) if poster_url else False

            # Resolve file paths
            mp4_disk = _disk_path_for_url(str(asset.id), mp4_url) if mp4_url else None
            poster_disk = _disk_path_for_url(str(asset.id), poster_url) if poster_url else None

            has_file = mp4_disk and os.path.exists(mp4_disk)
            valid_file = has_file and is_valid_mp4(mp4_disk)
            has_poster = poster_disk and os.path.exists(poster_disk)

            problems = []

            if not has_file:
                missing_file += 1
                problems.append("file=no")
            elif not valid_file:
                invalid_file += 1
                problems.append("valid=no")

            if not has_poster:
                missing_poster += 1
                problems.append("poster=no")

            if not has_mp4_metadata:
                missing_metadata += 1
                problems.append("metadata=no")

            if mp4_url and not mp4_is_hashed:
                old_style_mp4 += 1
                problems.append("mp4_hashed=no")

            if poster_url and not poster_is_hashed:
                old_style_poster += 1
                problems.append("poster_hashed=no")

            if not problems:
                continue

            print(
                f"{asset.id} state={asset.processing_state.value} "
                f"{' '.join(problems)} "
                f"mime={asset.mime_type} original={asset.original_filename}"
            )
            if asset.error_message:
                print(f"  error={asset.error_message}")

        print(
            f"\nMissing files: {missing_file}. "
            f"Invalid files: {invalid_file}. "
            f"Missing posters: {missing_poster}. "
            f"Missing derivative_paths.mp4 metadata: {missing_metadata}. "
            f"Old-style (unhashed) mp4 URLs: {old_style_mp4}. "
            f"Old-style (unhashed) poster URLs: {old_style_poster}."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

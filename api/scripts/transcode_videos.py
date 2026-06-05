"""
Transcode existing video assets to H.264/AAC MP4 for universal browser playback.
iPhone HEVC originals won't play in Safari's <video> tag — this produces a
web-safe derivative and updates derivative_paths in the database.

Derivative files are content-hashed and given immutable filenames so they can be
cached indefinitely by Cloudflare.

Run from the api container:

    docker compose exec api python /app/scripts/transcode_videos.py

Options:
  --force   Re-transcode even if an mp4 derivative already exists on disk
  --force-poster   Regenerate posters even if they already exist
"""

import hashlib
import os
import sys
import argparse
import subprocess
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.content import MediaAsset
from app.models.enums import MediaKind, MediaProcessingState

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/postmarked",
).replace("postgresql://", "postgresql+psycopg://", 1)

DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/derivatives")


def _derivative_hash(path: str) -> str:
    """Return the first 8 hex chars of the SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:8]


def _immutable_rename(tmp_path: str, asset_id, variant: str, ext: str) -> tuple[str, str]:
    """Hash a derivative file and atomically rename to its immutable filename.
    Returns (disk_path, public_url_path)."""
    hash8 = _derivative_hash(tmp_path)
    filename = f"{variant}-{hash8}.{ext}"
    final_path = os.path.join(DERIVATIVES_PATH, f"{asset_id}-{filename}")
    os.replace(tmp_path, final_path)
    return final_path, f"/media/{asset_id}/{filename}"


def probe_dimensions(path: str) -> tuple[int, int]:
    import json
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v",
        "-show_entries", "stream=width,height", "-of", "json", path,
    ]).decode()
    data = json.loads(raw or "{}")
    for stream in data.get("streams", []):
        w, h = stream.get("width"), stream.get("height")
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            return w, h
    raise ValueError("No valid video stream found")


def is_valid_mp4(path: str) -> bool:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.strip() == "h264"
    except Exception:
        return False


def transcode_video_to_mp4(file_path: str, mp4_path: str) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-i", file_path,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-profile:v", "main",
        "-level:v", "4.1",
        "-pix_fmt", "yuv420p",
        "-tag:v", "avc1",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-vf", (
            "scale=w='min(1920,iw)':h='min(1920,ih)':"
            "force_original_aspect_ratio=decrease,"
            "scale=trunc(iw/2)*2:trunc(ih/2)*2,"
            "format=yuv420p"
        ),
        mp4_path,
    ], check=True, capture_output=True)


def extract_poster(file_path: str, poster_path: str) -> None:
    subprocess.run([
        "ffmpeg",
        "-y",
        "-i",
        file_path,
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-update",
        "1",
        "-q:v",
        "2",
        poster_path,
    ], check=True, capture_output=True)


def _is_hashed_url(url: str) -> bool:
    """Check if a derivative_paths URL is a hashed (immutable) URL."""
    import re
    parts = url.rsplit("/", 1)
    return len(parts) == 2 and bool(re.match(r"^[a-z_]+-[0-9a-f]{8,}\.\w+$", parts[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-transcode even if mp4 already exists")
    parser.add_argument(
        "--force-poster",
        action="store_true",
        help="Regenerate poster images even if they already exist",
    )
    parser.add_argument(
        "--include-not-ready",
        action="store_true",
        help="Also repair pending/failed videos, not only READY rows",
    )
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    query = select(MediaAsset).where(MediaAsset.kind == MediaKind.VIDEO)
    if not args.include_not_ready:
        query = query.where(MediaAsset.processing_state == MediaProcessingState.READY)
    assets = db.execute(query).scalars().all()

    total = len(assets)
    print(f"Found {total} video asset(s) to process.")

    ok = skipped = errors = 0
    posters_ok = 0

    for i, asset in enumerate(assets, 1):
        paths = dict(asset.derivative_paths or {})
        file_path = asset.original_path
        if not file_path or not os.path.exists(file_path):
            print(f"[{i}/{total}] SKIP  {asset.id}  — original not found: {file_path}", file=sys.stderr)
            skipped += 1
            continue

        # --- Poster ---
        try:
            poster_needs_hash = not _is_hashed_url(paths.get("poster", ""))
            if args.force_poster or poster_needs_hash:
                tmp_poster = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp-poster.jpg")
                extract_poster(file_path, tmp_poster)
                _, poster_url = _immutable_rename(tmp_poster, asset.id, "poster", "jpg")
                paths["poster"] = poster_url
                posters_ok += 1
        except Exception as exc:
            errors += 1
            print(f"[{i}/{total}] ERROR {asset.id}  — poster failed: {exc}", file=sys.stderr)

        # --- MP4 ---
        mp4_needs_hash = not _is_hashed_url(paths.get("mp4", ""))

        # If we already have a hashed mp4 and --force is not set, just update metadata
        if not args.force and not mp4_needs_hash:
            changed = False
            if asset.processing_state != MediaProcessingState.READY:
                asset.processing_state = MediaProcessingState.READY
                asset.error_message = None
                changed = True
            if paths != (asset.derivative_paths or {}):
                asset.derivative_paths = paths
                changed = True
            if changed:
                db.commit()
                print(f"[{i}/{total}] FIXED {asset.id}  — metadata updated")
            else:
                print(f"[{i}/{total}] SKIP  {asset.id}  — already hashed (use --force to overwrite)")
            skipped += 1
            continue

        # Check for an existing unhashed mp4 on disk that we can just hash-rename
        old_mp4_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.mp4")
        if not args.force and mp4_needs_hash and os.path.exists(old_mp4_path) and is_valid_mp4(old_mp4_path):
            # Compute hash first — old file stays put until after DB commit so
            # a commit failure leaves the asset accessible via the legacy path.
            hash8 = _derivative_hash(old_mp4_path)
            filename = f"mp4-{hash8}.mp4"
            final_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}-{filename}")
            mp4_url = f"/media/{asset.id}/{filename}"

            paths["mp4"] = mp4_url
            asset.derivative_paths = paths
            asset.processing_state = MediaProcessingState.READY
            asset.error_message = None

            # Update dimensions if missing — probe before the rename
            if not asset.width or not asset.height:
                try:
                    w, h = probe_dimensions(old_mp4_path)
                    asset.width = w
                    asset.height = h
                    asset.aspect_ratio = round(w / h, 4)
                except Exception:
                    pass

            db.commit()  # commit first; if this fails, old file is still in place
            os.replace(old_mp4_path, final_path)  # rename only after successful commit
            print(f"[{i}/{total}] HASH  {asset.id}  — renamed existing mp4 to hashed filename")
            ok += 1
            continue

        # Full transcode needed
        try:
            tmp_mp4 = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp.mp4")
            transcode_video_to_mp4(file_path, tmp_mp4)

            w, h = probe_dimensions(tmp_mp4)
            asset.width = w
            asset.height = h
            asset.aspect_ratio = round(w / h, 4)

            _, mp4_url = _immutable_rename(tmp_mp4, asset.id, "mp4", "mp4")
            paths["mp4"] = mp4_url
            asset.derivative_paths = paths
            asset.processing_state = MediaProcessingState.READY
            asset.error_message = None
            db.commit()
            print(f"[{i}/{total}] OK    {asset.id}")
            ok += 1
        except Exception as exc:
            db.rollback()
            print(f"[{i}/{total}] ERROR {asset.id}  — {exc}", file=sys.stderr)
            errors += 1

    db.close()
    print(f"\nDone. {ok} transcoded, {posters_ok} poster(s) generated, {skipped} skipped, {errors} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

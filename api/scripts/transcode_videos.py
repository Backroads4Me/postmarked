"""
Transcode existing video assets to H.264/AAC MP4 for universal browser playback.
iPhone HEVC originals won't play in Safari's <video> tag — this produces a
web-safe derivative and updates derivative_paths in the database.

Run from the api container:

    docker compose exec api python /app/scripts/transcode_videos.py

Options:
  --force   Re-transcode even if an mp4 derivative already exists on disk
"""

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-transcode even if mp4 already exists")
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

    for i, asset in enumerate(assets, 1):
        mp4_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.mp4")

        if not args.force and os.path.exists(mp4_path):
            paths = dict(asset.derivative_paths or {})
            changed = False
            if paths.get("mp4") != f"/media/{asset.id}/mp4":
                paths["mp4"] = f"/media/{asset.id}/mp4"
                asset.derivative_paths = paths
                changed = True
            if asset.processing_state != MediaProcessingState.READY:
                asset.processing_state = MediaProcessingState.READY
                asset.error_message = None
                changed = True
            if changed:
                db.commit()
                print(f"[{i}/{total}] FIXED {asset.id}  — mp4 metadata updated")
            else:
                print(f"[{i}/{total}] SKIP  {asset.id}  — mp4 already exists (use --force to overwrite)")
            skipped += 1
            continue

        file_path = asset.original_path
        if not file_path or not os.path.exists(file_path):
            print(f"[{i}/{total}] SKIP  {asset.id}  — original not found: {file_path}", file=sys.stderr)
            skipped += 1
            continue

        try:
            transcode_video_to_mp4(file_path, mp4_path)

            w, h = probe_dimensions(mp4_path)
            asset.width = w
            asset.height = h
            asset.aspect_ratio = round(w / h, 4)

            paths = dict(asset.derivative_paths or {})
            paths["mp4"] = f"/media/{asset.id}/mp4"
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
    print(f"\nDone. {ok} transcoded, {skipped} skipped, {errors} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

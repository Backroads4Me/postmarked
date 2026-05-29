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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-transcode even if mp4 already exists")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    assets = db.execute(
        select(MediaAsset).where(
            MediaAsset.kind == MediaKind.VIDEO,
            MediaAsset.processing_state == MediaProcessingState.READY,
        )
    ).scalars().all()

    total = len(assets)
    print(f"Found {total} video asset(s) to process.")

    ok = skipped = errors = 0

    for i, asset in enumerate(assets, 1):
        mp4_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.mp4")

        if not args.force and os.path.exists(mp4_path):
            print(f"[{i}/{total}] SKIP  {asset.id}  — mp4 already exists (use --force to overwrite)")
            skipped += 1
            continue

        file_path = asset.original_path
        if not file_path or not os.path.exists(file_path):
            print(f"[{i}/{total}] SKIP  {asset.id}  — original not found: {file_path}", file=sys.stderr)
            skipped += 1
            continue

        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", file_path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-profile:v", "high", "-level:v", "4.1",
                "-c:a", "aac", "-b:a", "128k",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                "-movflags", "+faststart",
                mp4_path,
            ], check=True, capture_output=True)

            w, h = probe_dimensions(mp4_path)
            asset.width = w
            asset.height = h
            asset.aspect_ratio = round(w / h, 4)

            paths = dict(asset.derivative_paths or {})
            paths["mp4"] = f"/media/{asset.id}/mp4"
            asset.derivative_paths = paths
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

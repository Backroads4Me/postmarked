"""
Report video assets whose MP4 or poster derivative is missing or invalid.

Run from the api container:

    python /app/scripts/check_video_derivatives.py
"""

import os
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


def is_valid_mp4(path: str) -> bool:
    try:
        subprocess.run(
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
        return True
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

        for asset in assets:
            mp4_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.mp4")
            poster_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}-poster.jpg")
            has_file = os.path.exists(mp4_path)
            valid_file = has_file and is_valid_mp4(mp4_path)
            has_poster = os.path.exists(poster_path)
            has_metadata = bool((asset.derivative_paths or {}).get("mp4"))
            if has_file and valid_file and has_poster and has_metadata:
                continue

            if not has_file:
                missing_file += 1
            elif not valid_file:
                invalid_file += 1
            if not has_poster:
                missing_poster += 1
            if not has_metadata:
                missing_metadata += 1

            print(
                f"{asset.id} state={asset.processing_state.value} "
                f"file={'yes' if has_file else 'no'} "
                f"valid={'yes' if valid_file else 'no'} "
                f"poster={'yes' if has_poster else 'no'} "
                f"metadata={'yes' if has_metadata else 'no'} "
                f"mime={asset.mime_type} original={asset.original_filename}"
            )
            if asset.error_message:
                print(f"  error={asset.error_message}")

        print(
            f"Missing files: {missing_file}. "
            f"Invalid files: {invalid_file}. "
            f"Missing posters: {missing_poster}. "
            f"Missing derivative_paths.mp4 metadata: {missing_metadata}."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""
Report video assets whose MP4 derivative is missing on disk or in metadata.

Run from the api container:

    python /app/scripts/check_video_derivatives.py
"""

import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.content import MediaAsset
from app.models.enums import MediaKind

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/postmarked",
).replace("postgresql://", "postgresql+psycopg://", 1)

DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/derivatives")


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

        for asset in assets:
            mp4_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.mp4")
            has_file = os.path.exists(mp4_path)
            has_metadata = bool((asset.derivative_paths or {}).get("mp4"))
            if has_file and has_metadata:
                continue

            if not has_file:
                missing_file += 1
            if not has_metadata:
                missing_metadata += 1

            print(
                f"{asset.id} state={asset.processing_state.value} "
                f"file={'yes' if has_file else 'no'} "
                f"metadata={'yes' if has_metadata else 'no'} "
                f"mime={asset.mime_type} original={asset.original_filename}"
            )
            if asset.error_message:
                print(f"  error={asset.error_message}")

        print(
            f"Missing files: {missing_file}. "
            f"Missing derivative_paths.mp4 metadata: {missing_metadata}."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

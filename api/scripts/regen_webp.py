"""
One-time script: regenerate WebP derivatives for all existing photo assets.

Only rewrites the .webp file on disk — no database changes.
Run from the api container:

    docker exec -it api python /app/scripts/regen_webp.py

Or via docker compose (dev):

    docker compose -f compose.yaml -f docker/compose.dev.yaml \
        exec api python /app/scripts/regen_webp.py
"""

import os
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from PIL import Image

from app.models.content import MediaAsset
from app.models.enums import MediaKind, MediaProcessingState

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/postmarked",
).replace("postgresql://", "postgresql+psycopg://", 1)

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/originals")
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/derivatives")

WEBP_MAX = 1400
WEBP_QUALITY = 80


def main():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    assets = db.execute(
        select(MediaAsset).where(
            MediaAsset.kind == MediaKind.PHOTO,
            MediaAsset.processing_state == MediaProcessingState.READY,
        )
    ).scalars().all()

    total = len(assets)
    print(f"Found {total} photo asset(s) to reprocess.")

    ok = 0
    skipped = 0
    errors = 0

    for i, asset in enumerate(assets, 1):
        file_path = asset.original_path or os.path.join(ORIGINALS_PATH, f"{asset.id}.bin")
        if not os.path.exists(file_path):
            print(f"[{i}/{total}] SKIP  {asset.id}  — original not found: {file_path}")
            skipped += 1
            continue

        out_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.webp")
        try:
            with Image.open(file_path) as img:
                exif = img.getexif()
                if exif:
                    orientation = exif.get(274)
                    if orientation == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)

                img.thumbnail((WEBP_MAX, WEBP_MAX), Image.Resampling.LANCZOS)
                img.save(out_path, format="WEBP", quality=WEBP_QUALITY)

            print(f"[{i}/{total}] OK    {asset.id}")
            ok += 1
        except Exception as exc:
            print(f"[{i}/{total}] ERROR {asset.id}  — {exc}", file=sys.stderr)
            errors += 1

    db.close()
    print(f"\nDone. {ok} regenerated, {skipped} skipped (no original), {errors} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

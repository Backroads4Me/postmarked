"""
Regenerate all photo derivatives for existing assets: WebP (1400px), AVIF (1400px),
and small WebP (768px) for images that exceed that size. Also updates derivative_paths
in the database so the API serves the new variants.

Run from the api container:

    docker compose exec api python /app/scripts/regen_webp.py

Options:
  --force   Overwrite derivatives even if they already exist on disk (default: skip)
"""

import os
import sys
import argparse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

from app.models.content import MediaAsset
from app.models.enums import MediaKind, MediaProcessingState

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/postmarked",
).replace("postgresql://", "postgresql+psycopg://", 1)

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/originals")
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/derivatives")

FULL_MAX = 1400
SM_MAX = 768
WEBP_QUALITY = 80
AVIF_QUALITY = 70


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing derivatives")
    args = parser.parse_args()

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

        webp_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.webp")
        avif_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.avif")
        sm_path   = os.path.join(DERIVATIVES_PATH, f"{asset.id}_sm.webp")

        if not args.force and os.path.exists(avif_path):
            print(f"[{i}/{total}] SKIP  {asset.id}  — derivatives already exist (use --force to overwrite)")
            skipped += 1
            continue

        try:
            with Image.open(file_path) as img:
                exif = img.getexif()
                if exif:
                    orientation = exif.get(274)
                    if orientation == 3:   img = img.rotate(180, expand=True)
                    elif orientation == 6: img = img.rotate(270, expand=True)
                    elif orientation == 8: img = img.rotate(90, expand=True)

                original_width = img.width
                original_height = img.height

                # Full-size derivatives
                full = img.copy()
                full.thumbnail((FULL_MAX, FULL_MAX), Image.Resampling.LANCZOS)
                full.save(webp_path, format="WEBP", quality=WEBP_QUALITY)
                full.save(avif_path, quality=AVIF_QUALITY)

                derivative_paths: dict[str, str] = {
                    "webp": f"/media/{asset.id}/webp",
                    "avif": f"/media/{asset.id}/avif",
                }

                # Small variant only for images larger than 768px
                if original_width > SM_MAX or original_height > SM_MAX:
                    sm = img.copy()
                    sm.thumbnail((SM_MAX, SM_MAX), Image.Resampling.LANCZOS)
                    sm.save(sm_path, format="WEBP", quality=WEBP_QUALITY)
                    derivative_paths["webp_sm"] = f"/media/{asset.id}/webp_sm"

            asset.derivative_paths = derivative_paths
            db.commit()
            print(f"[{i}/{total}] OK    {asset.id}")
            ok += 1
        except Exception as exc:
            db.rollback()
            print(f"[{i}/{total}] ERROR {asset.id}  — {exc}", file=sys.stderr)
            errors += 1

    db.close()
    print(f"\nDone. {ok} reprocessed, {skipped} skipped, {errors} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

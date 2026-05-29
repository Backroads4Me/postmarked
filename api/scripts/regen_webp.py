"""
Regenerate all photo derivatives for existing assets: WebP (1400px), AVIF (1400px),
and small WebP (768px) for images that exceed that size. Also updates derivative_paths
in the database so the API serves the new variants.

Derivative files are content-hashed and given immutable filenames so they can be
cached indefinitely by Cloudflare.

Run from the api container:

    docker compose exec api python /app/scripts/regen_webp.py

Options:
  --force   Overwrite derivatives even if they already exist on disk (default: skip)
"""

import hashlib
import os
import re
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


def _is_hashed_url(url: str) -> bool:
    """Check if a derivative_paths URL is a hashed (immutable) URL."""
    parts = url.rsplit("/", 1)
    return len(parts) == 2 and bool(re.match(r"^[a-z_]+-[0-9a-f]{8,}\.\w+$", parts[1]))


def _all_photo_variants_hashed(dp: dict) -> bool:
    """Check if all photo derivative_paths entries are already hashed."""
    for key in ("webp", "avif"):
        url = dp.get(key, "")
        if not url or not _is_hashed_url(url):
            return False
    # webp_sm is optional — only check if present
    sm_url = dp.get("webp_sm", "")
    if sm_url and not _is_hashed_url(sm_url):
        return False
    return True


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

        dp = dict(asset.derivative_paths or {})

        if not args.force and _all_photo_variants_hashed(dp):
            print(f"[{i}/{total}] SKIP  {asset.id}  — derivatives already hashed (use --force to overwrite)")
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

                tmp_webp = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp.webp")
                tmp_avif = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp.avif")
                full.save(tmp_webp, format="WEBP", quality=WEBP_QUALITY)
                full.save(tmp_avif, quality=AVIF_QUALITY)

                _, webp_url = _immutable_rename(tmp_webp, asset.id, "webp", "webp")
                _, avif_url = _immutable_rename(tmp_avif, asset.id, "avif", "avif")

                derivative_paths: dict[str, str] = {
                    "webp": webp_url,
                    "avif": avif_url,
                }

                # Small variant only for images larger than 768px
                if original_width > SM_MAX or original_height > SM_MAX:
                    sm = img.copy()
                    sm.thumbnail((SM_MAX, SM_MAX), Image.Resampling.LANCZOS)
                    tmp_sm = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp_sm.webp")
                    sm.save(tmp_sm, format="WEBP", quality=WEBP_QUALITY)
                    _, sm_url = _immutable_rename(tmp_sm, asset.id, "webp_sm", "webp")
                    derivative_paths["webp_sm"] = sm_url

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

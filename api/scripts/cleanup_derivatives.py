"""
Remove unreferenced derivative files from DERIVATIVES_PATH.

Connects to the database and collects all filesystem paths referenced by any
asset's derivative_paths.  Walks DERIVATIVES_PATH and deletes any file not in
that set.

Run only after the backfill is verified; never run automatically as part of
the worker.

Run from the api container:

    docker compose exec api python /app/scripts/cleanup_derivatives.py

Options:
  --dry-run   List files that would be deleted without actually removing them
"""

import os
import re
import sys
import argparse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.content import MediaAsset

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/postmarked",
).replace("postgresql://", "postgresql+psycopg://", 1)

DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/derivatives")
ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/originals")

_HASHED_FILENAME_RE = re.compile(r"^[a-z_]+-[0-9a-f]{8,}\.\w+$")


def _referenced_paths(db) -> set[str]:
    """Collect all derivative filesystem paths referenced by any MediaAsset."""
    assets = db.execute(select(MediaAsset)).scalars().all()
    paths: set[str] = set()
    for asset in assets:
        dp = asset.derivative_paths or {}
        for variant, url_path in dp.items():
            if not url_path:
                continue
            parts = url_path.rsplit("/", 1)
            if len(parts) != 2:
                continue
            filename = parts[1]
            if _HASHED_FILENAME_RE.match(filename):
                paths.add(os.path.join(DERIVATIVES_PATH, f"{asset.id}-{filename}"))
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
                paths.add(os.path.join(DERIVATIVES_PATH, disk_filename))

        # Safety net: protect legacy-named files for every asset regardless of
        # derivative_paths contents.  Covers assets with derivative_paths=NULL
        # (FAILED/pre-backfill state) that still have on-disk derivatives.
        for suffix in (".webp", ".avif", "_sm.webp", ".mp4", "-poster.jpg"):
            paths.add(os.path.join(DERIVATIVES_PATH, f"{asset.id}{suffix}"))

    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Remove unreferenced derivative files from DERIVATIVES_PATH."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be deleted without actually removing them",
    )
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        referenced = _referenced_paths(db)
        print(f"Found {len(referenced)} referenced derivative path(s) in the database.")

        if not os.path.exists(DERIVATIVES_PATH):
            print(f"DERIVATIVES_PATH does not exist: {DERIVATIVES_PATH}")
            return

        # Walk the derivatives directory and find unreferenced files
        all_files = []
        for root, dirs, files in os.walk(DERIVATIVES_PATH):
            for filename in files:
                filepath = os.path.join(root, filename)
                all_files.append(filepath)

        print(f"Found {len(all_files)} total file(s) in {DERIVATIVES_PATH}.")

        unreferenced = [f for f in all_files if f not in referenced]
        referenced_count = len(all_files) - len(unreferenced)

        print(f"Referenced: {referenced_count}. Unreferenced: {len(unreferenced)}.")

        if not unreferenced:
            print("Nothing to clean up.")
            return

        deleted = 0
        errors = 0
        freed_bytes = 0
        for filepath in unreferenced:
            try:
                size = os.path.getsize(filepath)
                if args.dry_run:
                    print(f"  would delete: {filepath} ({size:,} bytes)")
                else:
                    os.remove(filepath)
                    deleted += 1
                freed_bytes += size
            except Exception as exc:
                print(f"  ERROR: {filepath} — {exc}", file=sys.stderr)
                errors += 1

        freed_mb = freed_bytes / (1024 * 1024)
        if args.dry_run:
            print(f"\nDry run complete. Would delete {len(unreferenced)} file(s) ({freed_mb:.1f} MB).")
        else:
            print(f"\nDeleted {deleted} file(s) ({freed_mb:.1f} MB freed). Errors: {errors}.")
        if errors:
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

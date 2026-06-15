"""
Admin backup endpoints — export and import a full ZIP archive for migration.
"""
import asyncio
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from geoalchemy2 import WKTElement
from geoalchemy2.types import Geography, Geometry
from sqlalchemy import func, inspect as sa_inspect, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.user import User
from app.schemas.backup import BackupManifest, ImportResult
from app.services.audit import log_audit_event
from app.services.db_backup import pg_conn_args
from app.services.media_storage import DERIVATIVES_PATH, ORIGINALS_PATH

router = APIRouter(prefix="/backup", tags=["admin-backup"])

_VERSION_PATH = os.path.join(os.path.dirname(__file__), "../../../../VERSION")


def _read_app_version() -> str:
    try:
        with open(_VERSION_PATH) as f:
            return f.read().strip()
    except OSError:
        return "unknown"


async def _run_pg_tool(tool: str, *tool_args: str, env: dict[str, str]) -> None:
    """Run pg_dump/pg_restore, raising HTTPException on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            tool, *tool_args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=f"{tool} is not installed in the API image — rebuild with postgresql-client-16.",
        )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"{tool} failed (exit {proc.returncode}): {stderr.decode(errors='replace')[:1000]}",
        )


def _restore_media_files(zf: zipfile.ZipFile, zip_names: set[str]) -> int:
    """Wipe and repopulate the derivatives directory from the archive."""
    for media_dir in (ORIGINALS_PATH, DERIVATIVES_PATH):
        if os.path.exists(media_dir):
            for entry in os.scandir(media_dir):
                if entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(entry.path)
                else:
                    os.remove(entry.path)
        else:
            os.makedirs(media_dir)

    copied = 0
    for zip_path in zip_names:
        if zip_path.startswith("media/derivatives/"):
            dest = os.path.join(DERIVATIVES_PATH, os.path.basename(zip_path))
            with open(dest, "wb") as fh:
                fh.write(zf.read(zip_path))
            copied += 1
    return copied


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    return value


async def _query_all(session: AsyncSession, model_class) -> list[dict]:
    """Query all rows, converting geometry columns to WKT via ST_AsText (no shapely needed)."""
    from sqlalchemy import select
    mapper = sa_inspect(model_class)
    cols = []
    for attr in mapper.mapper.column_attrs:
        col = attr.columns[0]
        if isinstance(col.type, (Geography, Geometry)):
            cols.append(func.ST_AsText(col).label(attr.key))
        else:
            cols.append(col.label(attr.key))
    rows = (await session.execute(select(*cols))).mappings().all()
    return [
        {k: _serialize_value(v) for k, v in row.items()}
        for row in rows
    ]


def _serialize_stop_backup_row(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for key in ("start_date", "end_date"):
        value = data.get(key)
        if isinstance(value, str) and "T" in value:
            data[key] = value.split("T", 1)[0]
    return data


def _geo_col_keys(model_class) -> set[str]:
    """Return column keys that hold Geography/Geometry values."""
    mapper = sa_inspect(model_class)
    return {
        a.key
        for a in mapper.mapper.column_attrs
        if isinstance(a.columns[0].type, (Geography, Geometry))
    }


# Reverse-dependency order for TRUNCATE — CASCADE handles FK edges.
_TRUNCATE_TABLES = ", ".join([
    "audit_log",
    "notification_log",
    '"like"',
    "comment",
    "media_asset",
    "post",
    "point_of_interest",
    "stop",
    "trip",
    "import_run",
    "site_text_section",
    "notification_preference",
    '"user"',
    "pre_approved_email",
    "site_config",
])


@router.get("/export")
async def export_backup(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """Download a ZIP archive of all content, users, and media derivatives.

    The database is captured with `pg_dump --data-only` (custom format) rather
    than per-table JSON: it is transactionally consistent, schema-complete, and
    restores via pg_restore. The target instance supplies the schema via
    `alembic upgrade head`, so a data-only dump is sufficient for migration.
    """
    from sqlalchemy import select
    from app.models.content import MediaAsset, PointOfInterest, Post, Stop, SiteTextSection, Trip
    from app.models.system import Comment, Like, PreApprovedEmail, SiteConfig
    from app.models.user import NotificationPreference, User as UserModel

    tmp = tempfile.NamedTemporaryFile(prefix="postmarked-backup-", suffix=".zip", delete=False)
    tmp_path = tmp.name
    tmp.close()
    dump_fd, dump_path = tempfile.mkstemp(prefix="postmarked-db-", suffix=".dump")
    os.close(dump_fd)
    entity_counts: dict[str, int] = {}

    try:
        # Consistent, schema-complete data dump. spatial_ref_sys (PostGIS) and
        # alembic_version are owned by the target's own migrations — exclude them.
        pg_args, pg_env = pg_conn_args()
        await _run_pg_tool(
            "pg_dump", *pg_args,
            "--data-only", "--format=custom",
            "--exclude-table=spatial_ref_sys",
            "--exclude-table=alembic_version",
            "-f", dump_path,
            env=pg_env,
        )

        # Row counts for the manifest (informational; cheap COUNT(*) per table).
        count_models = {
            "site_config": SiteConfig, "pre_approved_emails": PreApprovedEmail,
            "users": UserModel, "notification_preferences": NotificationPreference,
            "trips": Trip, "stops": Stop, "pois": PointOfInterest, "posts": Post,
            "media_assets": MediaAsset, "site_text_sections": SiteTextSection,
            "comments": Comment, "likes": Like,
        }
        for name, model in count_models.items():
            entity_counts[name] = (
                await session.execute(select(func.count()).select_from(model))
            ).scalar_one()

        # media_rows drives derivative-file bundling (resolves on-disk paths).
        media_rows = await _query_all(session, MediaAsset)

        with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Media is already-compressed; store the dump without re-deflating media.
            zf.write(dump_path, "db.dump")

            # Bundle derivative files from disk — read paths from derivative_paths.
            import re
            _HASHED_FILENAME_RE = re.compile(r"^[a-z0-9_]+-[0-9a-f]{8,}\.\w+$")
            for row in media_rows:
                asset_id = row["id"]
                dp = row.get("derivative_paths") or {}
                added_paths: set[str] = set()
                for variant, url_path in dp.items():
                    if not url_path:
                        continue
                    # Extract filename from URL path like /media/{id}/{filename}
                    parts = url_path.rsplit("/", 1)
                    if len(parts) != 2:
                        continue
                    filename = parts[1]
                    # Determine disk path based on whether filename is hashed
                    if _HASHED_FILENAME_RE.match(filename):
                        disk_path = os.path.join(DERIVATIVES_PATH, f"{asset_id}-{filename}")
                    else:
                        # Legacy filenames — map variant to old naming convention
                        legacy_map = {
                            "webp": f"{asset_id}.webp",
                            "avif": f"{asset_id}.avif",
                            "webp_sm": f"{asset_id}_sm.webp",
                            "mp4": f"{asset_id}.mp4",
                            "poster": f"{asset_id}-poster.jpg",
                        }
                        disk_filename = legacy_map.get(variant, filename)
                        disk_path = os.path.join(DERIVATIVES_PATH, disk_filename)
                    if os.path.exists(disk_path):
                        archive_name = os.path.basename(disk_path)
                        zf.write(disk_path, f"media/derivatives/{archive_name}")
                        added_paths.add(disk_path)
                # Safety net: include legacy-named files for assets whose
                # derivative_paths is NULL or missing (FAILED/pre-backfill state).
                for suffix in (".webp", ".avif", "_sm.webp", ".mp4", "-poster.jpg"):
                    legacy_path = os.path.join(DERIVATIVES_PATH, f"{asset_id}{suffix}")
                    if legacy_path not in added_paths and os.path.exists(legacy_path):
                        zf.write(legacy_path, f"media/derivatives/{asset_id}{suffix}")

            zf.writestr(
                "manifest.json",
                BackupManifest(
                    app_version=_read_app_version(),
                    created_at=datetime.utcnow(),
                    entity_counts=entity_counts,
                    format="pgdump",
                ).model_dump_json(indent=2),
            )

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"postmarked-backup-{date_str}.zip"

        await log_audit_event(session, user.id, "EXPORT_BACKUP", "backup", uuid.uuid4(), entity_counts)
        await session.commit()

        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename=filename,
            background=BackgroundTask(os.remove, tmp_path),
        )
    except Exception:
        for path in (tmp_path, dump_path):
            if os.path.exists(path):
                os.remove(path)
        raise
    finally:
        # The dump is now inside the zip; the success path no longer needs it.
        if os.path.exists(dump_path):
            os.remove(dump_path)


async def _import_pgdump(
    session: AsyncSession,
    user: User,
    zf: zipfile.ZipFile,
    zip_names: set[str],
    manifest: BackupManifest,
) -> ImportResult:
    """Restore a pg_dump-based backup: TRUNCATE, pg_restore --data-only, then media.

    The TRUNCATE is committed before pg_restore runs because pg_restore opens its
    own connection and must see empty tables. This is destructive and irreversible
    once started — the admin UI warns before invoking it.
    """
    dump_fd, dump_path = tempfile.mkstemp(prefix="postmarked-restore-", suffix=".dump")
    with os.fdopen(dump_fd, "wb") as fh:
        fh.write(zf.read("db.dump"))

    try:
        # Truncate every public table the dump can target (same exclusions as
        # pg_dump above), so the wipe scope always matches the restore scope even
        # as the schema grows. Commit it so pg_restore's own connection sees the
        # tables empty.
        tables = (await session.execute(text(
            "SELECT quote_ident(tablename) FROM pg_tables "
            "WHERE schemaname = 'public' "
            "AND tablename NOT IN ('spatial_ref_sys', 'alembic_version')"
        ))).scalars().all()
        if tables:
            await session.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
        await session.commit()

        pg_args, pg_env = pg_conn_args()
        # --disable-triggers loads rows regardless of FK order (no manual deferral);
        # --single-transaction rolls the whole load back on any error.
        await _run_pg_tool(
            "pg_restore", *pg_args,
            "--data-only", "--disable-triggers", "--no-owner",
            "--single-transaction",
            dump_path,
            env=pg_env,
        )
    finally:
        if os.path.exists(dump_path):
            os.remove(dump_path)

    media_files_copied = _restore_media_files(zf, zip_names)

    await log_audit_event(
        session, user.id, "IMPORT_BACKUP", "backup", uuid.uuid4(), manifest.entity_counts
    )
    await session.commit()
    return ImportResult(entity_counts=manifest.entity_counts, media_files_copied=media_files_copied)


@router.post("/import", response_model=ImportResult)
async def import_backup(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """
    Upload a backup ZIP and fully replace all data on this instance.
    WARNING: wipes all existing content before restoring.
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive.")

    with tempfile.TemporaryFile() as tmp:
        while chunk := await file.read(1024 * 1024):
            tmp.write(chunk)
        tmp.seek(0)
        try:
            with zipfile.ZipFile(tmp) as zf:
                zip_names = set(zf.namelist())
                if "manifest.json" not in zip_names:
                    raise HTTPException(status_code=400, detail="Archive is missing manifest.json.")

                try:
                    manifest = BackupManifest(**json.loads(zf.read("manifest.json")))
                except Exception:
                    raise HTTPException(status_code=400, detail="manifest.json is malformed.")

                # New-format backups carry a pg_dump archive — restore via pg_restore.
                if "db.dump" in zip_names:
                    return await _import_pgdump(session, user, zf, zip_names, manifest)

                # ---- Legacy JSON path (backups exported before the pg_dump switch) ----
                # Full wipe — CASCADE clears all FK-dependent rows automatically.
                await session.execute(text(f"TRUNCATE {_TRUNCATE_TABLES} CASCADE"))
                await session.flush()

                entity_counts: dict[str, int] = {}

                def _load(archive_name: str) -> list[dict]:
                    path = f"data/{archive_name}.json"
                    return json.loads(zf.read(path)) if path in zip_names else []

                def _restore_value(archive_name: str, key: str, val: Any) -> Any:
                    if archive_name == "stops" and key in {"start_date", "end_date"} and isinstance(val, str):
                        date_part = val.split("T", 1)[0]
                        try:
                            date.fromisoformat(date_part)
                        except ValueError:
                            return val
                        return f"{date_part}T12:00:00+00:00"
                    return val

                async def _restore(archive_name: str, model_class, skip_cols: set[str] | None = None):
                    rows = _load(archive_name)
                    geo_keys = _geo_col_keys(model_class)
                    valid_keys = {attr.key for attr in sa_inspect(model_class).mapper.column_attrs}
                    for row in rows:
                        data: dict[str, Any] = {}
                        for key, val in row.items():
                            if key not in valid_keys or (skip_cols and key in skip_cols):
                                continue
                            val = _restore_value(archive_name, key, val)
                            if val is None:
                                data[key] = None
                            elif key in geo_keys:
                                data[key] = WKTElement(val, srid=4326)
                            elif key == "id" or key.endswith("_id"):
                                try:
                                    data[key] = uuid.UUID(val)
                                except (ValueError, AttributeError):
                                    data[key] = val
                            else:
                                data[key] = val
                        session.add(model_class(**data))
                    await session.flush()
                    entity_counts[archive_name] = len(rows)

                from app.models.content import MediaAsset, PointOfInterest, Post, Stop, SiteTextSection, Trip
                from app.models.system import Comment, Like, PreApprovedEmail, SiteConfig
                from app.models.user import NotificationPreference, User as UserModel

                # Stash circular cover FKs; insert trips/stops without them first.
                trip_rows = _load("trips")
                stop_rows = _load("stops")
                media_rows = _load("media_assets")
                trip_cover_map = {r["id"]: r.get("cover_media_id") for r in trip_rows if r.get("cover_media_id")}
                stop_cover_map = {r["id"]: r.get("cover_media_id") for r in stop_rows if r.get("cover_media_id")}
                # media_asset.post_id is a FK to post, but posts aren't restored until after media — defer it.
                media_post_map = {r["id"]: r.get("post_id") for r in media_rows if r.get("post_id")}

                await _restore("site_config", SiteConfig)
                await _restore("pre_approved_emails", PreApprovedEmail)
                await _restore("users", UserModel)
                await _restore("notification_preferences", NotificationPreference)
                await _restore("trips", Trip, skip_cols={"cover_media_id", "source_import_run_id"})
                await _restore("stops", Stop, skip_cols={"cover_media_id"})
                await _restore("pois", PointOfInterest)
                await _restore("media_assets", MediaAsset, skip_cols={"post_id"})
                await _restore("posts", Post)
                await _restore("site_text_sections", SiteTextSection)
                await _restore("comments", Comment)
                await _restore("likes", Like)

                # Patch back all deferred circular FK references.
                for trip_id_str, cover_id_str in trip_cover_map.items():
                    await session.execute(
                        update(Trip)
                        .where(Trip.id == uuid.UUID(trip_id_str))
                        .values(cover_media_id=uuid.UUID(cover_id_str))
                    )
                for stop_id_str, cover_id_str in stop_cover_map.items():
                    await session.execute(
                        update(Stop)
                        .where(Stop.id == uuid.UUID(stop_id_str))
                        .values(cover_media_id=uuid.UUID(cover_id_str))
                    )
                for media_id_str, post_id_str in media_post_map.items():
                    await session.execute(
                        update(MediaAsset)
                        .where(MediaAsset.id == uuid.UUID(media_id_str))
                        .values(post_id=uuid.UUID(post_id_str))
                    )

                # Wipe and repopulate the derivatives directory from the archive.
                media_files_copied = _restore_media_files(zf, zip_names)

                await session.commit()
                return ImportResult(entity_counts=entity_counts, media_files_copied=media_files_copied)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid ZIP archive.")


@router.post("/snapshot")
async def create_db_snapshot(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """Queue an on-demand server-side pg_dump into the backups directory.

    The dump is written on the Celery worker (same image, which has
    postgresql-client-16) so the request returns immediately. Combined with the
    scheduled task, this keeps a rotating set of dumps under BACKUPS_PATH that an
    operator can rsync alongside the derivatives directory.
    """
    # Imported lazily: app.tasks pulls in heavy media-processing deps.
    from app.tasks import create_db_backup

    create_db_backup.delay()
    await log_audit_event(session, user.id, "SNAPSHOT_DB", "backup", uuid.uuid4(), {})
    await session.commit()
    return {"status": "queued", "detail": "Database snapshot started on the server."}

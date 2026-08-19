import hashlib
import os
import uuid
import logging
import json
import re
from html import escape
from celery import Celery
from celery.schedules import crontab
import subprocess
from datetime import datetime, timedelta, timezone
from PIL import Image
import blurhash
from pillow_heif import register_heif_opener

register_heif_opener()
from sqlalchemy import and_, create_engine, or_, select, text, update
from sqlalchemy.orm import sessionmaker

from app.models.content import MediaAsset, Post, SiteTextSection, Stop
from app.models.enums import ApprovalState, MediaKind, MediaProcessingState, NotificationFrequency, PostStatus, StopStatus, UserRole, Visibility
from app.models.system import NotificationLog
from app.models.user import NotificationPreference, User
from app.services.mailer import send_email
from app.services.original_retention import delete_original_after_success

logger = logging.getLogger(__name__)

# Every ffmpeg/ffprobe call is bounded: an unkillable transcode otherwise pins a
# prefork worker child forever, and the same default queue carries notifications
# and the nightly backup.
FFPROBE_TIMEOUT_SECONDS = int(os.getenv("FFPROBE_TIMEOUT_SECONDS", "60"))
FFMPEG_TIMEOUT_SECONDS = int(os.getenv("FFMPEG_TIMEOUT_SECONDS", "3600"))
MEDIA_PENDING_REQUEUE_SECONDS = int(os.getenv("MEDIA_PENDING_REQUEUE_SECONDS", "3600"))
# Longer than the global Celery hard limit so an active task is never treated
# as abandoned while it can still be running normally.
MEDIA_PROCESSING_LEASE_SECONDS = int(os.getenv("MEDIA_PROCESSING_LEASE_SECONDS", "7200"))
TUS_UPLOAD_RETENTION_SECONDS = int(os.getenv("TUS_UPLOAD_RETENTION_SECONDS", "604800"))
TUS_SIDECAR_MAX_BYTES = 64 * 1024

# Pillow warns but does not raise between 89M and 178M pixels. A 12000x12000 PNG
# is ~150 KB on the wire and ~430 MB decoded, and the task holds several copies,
# so cap well below that and fail cleanly instead of being OOM-killed.
Image.MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(50_000_000)))

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
_DATABASE_URL_RAW = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/postmarked")
DATABASE_URL_SYNC = _DATABASE_URL_RAW.replace("postgresql://", "postgresql+psycopg://", 1)

MEDIA_DIR = os.getenv("MEDIA_DIR", "/media")
ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", os.path.join(MEDIA_DIR, "originals"))
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", os.path.join(MEDIA_DIR, "derivatives"))

celery_app = Celery("postmarked_tasks", broker=REDIS_URL)
celery_app.conf.timezone = os.getenv("CELERY_TIMEZONE", "UTC")
# Bound every task, and redeliver rather than drop when a worker child dies:
# with the defaults a message is acked on receipt, so an OOM-killed transcode
# left its asset PENDING forever with nothing to retry it.
celery_app.conf.task_time_limit = int(os.getenv("CELERY_TASK_TIME_LIMIT", "5400"))
celery_app.conf.task_soft_time_limit = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "5100"))
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.beat_schedule = {
    "weekly-digest-monday-morning": {
        "task": "dispatch_weekly_digest",
        "schedule": crontab(hour=8, minute=0, day_of_week="monday"),
    },
    "refresh-weather-hourly": {
        "task": "refresh_weather",
        "schedule": crontab(minute=0),
    },
    "sweep-stale-media-hourly": {
        "task": "sweep_stale_media",
        "schedule": crontab(minute=30),
    },
    "daily-db-backup": {
        "task": "create_db_backup",
        "schedule": crontab(
            hour=int(os.getenv("BACKUP_HOUR", "3")),
            minute=int(os.getenv("BACKUP_MINUTE", "0")),
        ),
    },
}

engine = create_engine(DATABASE_URL_SYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _base_url() -> str:
    return os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")


def _post_url(post: Post) -> str:
    if post.trip and post.stop:
        return f"{_base_url()}/trips/{post.trip.slug}/stops/{post.stop.slug}/posts/{post.slug}"
    return f"{_base_url()}/timeline"


def _post_is_published(post: Post) -> bool:
    return post.status == PostStatus.PUBLISHED


def _approved_notification_users(db, frequency: NotificationFrequency):
    return (
        db.execute(
            select(User, NotificationPreference)
            .join(NotificationPreference, NotificationPreference.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.approval_state == ApprovalState.APPROVED,
                NotificationPreference.email_opted_in.is_(True),
                NotificationPreference.frequency == frequency,
            )
        )
        .all()
    )


def _notification_already_logged(db, user_id, kind: str) -> bool:
    return (
        db.execute(
            select(NotificationLog.id)
            .where(NotificationLog.user_id == user_id, NotificationLog.kind == kind)
            .limit(1)
        )
        .first()
        is not None
    )


def _record_notification(db, user_id, kind: str, payload: dict, sent: bool, error_message: str | None = None):
    db.add(
        NotificationLog(
            user_id=user_id,
            kind=kind,
            payload=payload,
            sent_at=datetime.now(timezone.utc) if sent else None,
            delivery_status="sent" if sent else "skipped",
            error_message=error_message,
        )
    )


_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HTML_IMAGE_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_MEDIA_DESCRIPTION_LINE_RE = re.compile(
    r"^\s*(?:image|photo|media)\s+(?:description|caption|alt text)\s*:.*$",
    re.IGNORECASE,
)


def _post_email_text(body: str | None) -> str:
    text = _MARKDOWN_IMAGE_RE.sub("", body or "")
    text = _HTML_IMAGE_RE.sub("", text)
    lines = [
        line.rstrip()
        for line in text.splitlines()
        if not _MEDIA_DESCRIPTION_LINE_RE.match(line)
    ]
    cleaned = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _email_body_html(body: str) -> str:
    paragraphs = [part.strip() for part in body.split("\n\n") if part.strip()]
    if not paragraphs:
        return ""
    return "".join(
        f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
    )


def _fill_post_template(template: str, post_title: str) -> str:
    return (template or "").replace("{post_title}", post_title)


def _post_email_bodies(post: Post, db) -> tuple[str, str, str]:
    url = _post_url(post)
    body = _post_email_text(post.body)

    config = db.execute(
        select(SiteTextSection).where(
            SiteTextSection.page_key == "email",
            SiteTextSection.section_key == "post_notification",
        )
    ).scalar_one_or_none()

    default_subject = "New update from the road"
    default_cta = "See the photos"

    if config:
        # Plain substitution, not str.format: site text is admin-editable prose,
        # and any stray brace — "{post_tittle}", "{0}", or a literal "{" — raised
        # out of here before the recipient loop, so nobody was emailed and
        # nothing was logged.
        subject = _fill_post_template(config.heading or default_subject, post.title)
        intro = _fill_post_template(config.body, post.title) if config.body else None
        cta = config.cta_label or default_cta
    else:
        subject = default_subject
        intro = None
        cta = default_cta

    if intro:
        text = f"{intro}\n\n{post.title}\n\n{body}\n\n{cta}: {url}\n"
        html = f"<p>{escape(intro)}</p>" f"<h1>{escape(post.title)}</h1>"
        html += _email_body_html(body)
        html += f'<p><a href="{url}">{escape(cta)}</a></p>'
    else:
        text = f"{post.title}\n\n{body}\n\n{cta}: {url}\n"
        html = f"<h1>{escape(post.title)}</h1>"
        html += _email_body_html(body)
        html += f'<p><a href="{url}">{escape(cta)}</a></p>'

    return subject, text, html

def _dms_to_decimal(dms, ref) -> float | None:
    """Convert EXIF DMS tuple + hemisphere ref to signed decimal degrees."""
    if not dms or not ref:
        return None
    try:
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        decimal = degrees + minutes / 60 + seconds / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def _probe_video_dimensions(file_path: str) -> tuple[int, int]:
    """Return the first valid video stream dimensions from ffprobe JSON output."""
    dim_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        file_path,
    ]
    raw = subprocess.check_output(dim_cmd, timeout=FFPROBE_TIMEOUT_SECONDS).decode("utf-8")
    data = json.loads(raw or "{}")
    for stream in data.get("streams", []):
        width = stream.get("width")
        height = stream.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return width, height
    raise ValueError("No video stream with numeric width and height found")


def _probe_duration(file_path: str) -> float:
    """Return container duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    out = subprocess.check_output(
        cmd, stderr=subprocess.STDOUT, timeout=FFPROBE_TIMEOUT_SECONDS
    ).decode("utf-8").strip()
    return float(out)


def _assert_transcode_complete(src_path: str, dst_path: str) -> None:
    """
    Raise ValueError if the transcoded output is meaningfully shorter than the source.
    iPhone MOV files have the moov atom at the front so ffprobe reports a full
    duration even when the mdat payload is truncated; this catches that case.
    """
    src_dur = _probe_duration(src_path)
    dst_dur = _probe_duration(dst_path)
    # Allow 2 s or 2% tolerance for encoder rounding differences
    tolerance = max(2.0, src_dur * 0.02)
    if dst_dur < src_dur - tolerance:
        raise ValueError(
            f"Transcoded video is truncated: source={src_dur:.1f}s output={dst_dur:.1f}s — "
            "the original upload may be incomplete"
        )


def _transcode_video_to_mp4(file_path: str, mp4_path: str) -> None:
    """Create an iOS/Safari-friendly H.264/AAC MP4 derivative."""
    subprocess.run([
        "ffmpeg", "-y", "-i", file_path,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-maxrate", "8000k",
        "-bufsize", "16000k",
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
    ], check=True, timeout=FFMPEG_TIMEOUT_SECONDS)


def _derivative_hash(path: str) -> str:
    """Return the first 8 hex chars of the SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:8]


def _immutable_derivative(
    tmp_path: str,
    asset_id: uuid.UUID,
    variant: str,
    ext: str,
) -> tuple[str, str]:
    """
    Hash a generated derivative file and atomically rename it to its immutable
    filename.  Returns (disk_path, public_url_path).
    """
    hash8 = _derivative_hash(tmp_path)
    filename = f"{variant}-{hash8}.{ext}"
    final_path = os.path.join(DERIVATIVES_PATH, f"{asset_id}-{filename}")
    os.replace(tmp_path, final_path)
    return final_path, f"/media/{asset_id}/{filename}"


def _media_lock_key(asset_id: uuid.UUID) -> int:
    """Map an asset UUID to PostgreSQL's signed 64-bit advisory-lock key."""
    return int.from_bytes(asset_id.bytes[:8], byteorder="big", signed=True)


def _acquire_media_lock(db, asset_id: uuid.UUID) -> bool:
    result = db.execute(
        text("SELECT pg_try_advisory_lock(:lock_key)"),
        {"lock_key": _media_lock_key(asset_id)},
    )
    return bool(result.scalar_one())


def _release_media_lock(db, asset_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_unlock(:lock_key)"),
        {"lock_key": _media_lock_key(asset_id)},
    )


def _claim_media_asset(db, asset_id: uuid.UUID, *, now: datetime | None = None) -> bool:
    """Atomically claim pending work or a processing lease that has expired."""
    claimed_at = now or datetime.now(timezone.utc)
    expired_before = claimed_at - timedelta(seconds=MEDIA_PROCESSING_LEASE_SECONDS)
    result = db.execute(
        update(MediaAsset)
        .where(
            MediaAsset.id == asset_id,
            or_(
                MediaAsset.processing_state == MediaProcessingState.PENDING,
                and_(
                    MediaAsset.processing_state == MediaProcessingState.PROCESSING,
                    MediaAsset.updated_at < expired_before,
                ),
            ),
        )
        .values(
            processing_state=MediaProcessingState.PROCESSING,
            error_message=None,
            updated_at=claimed_at,
        )
        .returning(MediaAsset.id)
    )
    claimed = result.scalar_one_or_none() is not None
    if claimed:
        db.commit()
    return claimed


def _paused_tus_upload_activity(file_id: str) -> float | None:
    """Return the latest activity time for a structurally valid paused upload."""
    try:
        uuid.UUID(file_id)
    except ValueError:
        return None

    info_path = os.path.join(ORIGINALS_PATH, f"{file_id}.json")
    bin_path = os.path.join(ORIGINALS_PATH, f"{file_id}.bin")
    try:
        info_stat = os.stat(info_path)
        bin_stat = os.stat(bin_path)
        if info_stat.st_size > TUS_SIDECAR_MAX_BYTES:
            return None
        with open(info_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(state, dict) or not isinstance(state.get("metadata"), dict):
        return None
    offset = state.get("offset")
    upload_length = state.get("upload_length")
    if (
        not isinstance(offset, int)
        or isinstance(offset, bool)
        or not isinstance(upload_length, int)
        or isinstance(upload_length, bool)
        or offset < 0
        or upload_length < 1
        or offset >= upload_length
        or bin_stat.st_size < offset
        or bin_stat.st_size > upload_length
    ):
        return None
    return max(info_stat.st_mtime, bin_stat.st_mtime)


def _remove_stale_upload_artifacts(known: set[str], *, now: datetime) -> int:
    """Expire upload pairs by validity and last activity, never by age alone."""
    if not os.path.isdir(ORIGINALS_PATH):
        return 0

    groups: dict[str, list[os.DirEntry]] = {}
    for entry in os.scandir(ORIGINALS_PATH):
        if not entry.is_file() or not entry.name.endswith((".bin", ".json")):
            continue
        stem = entry.name.rsplit(".", 1)[0]
        groups.setdefault(stem, []).append(entry)

    orphan_cutoff = now.timestamp() - MEDIA_PENDING_REQUEUE_SECONDS
    paused_cutoff = now.timestamp() - TUS_UPLOAD_RETENTION_SECONDS
    removed = 0
    for stem, entries in groups.items():
        if stem in known:
            continue
        activity = _paused_tus_upload_activity(stem)
        cutoff = paused_cutoff if activity is not None else orphan_cutoff
        try:
            latest_mtime = max(entry.stat().st_mtime for entry in entries)
        except OSError:
            logger.exception("Could not inspect upload artifacts for %s", stem)
            continue
        if latest_mtime >= cutoff:
            continue
        for entry in entries:
            try:
                os.remove(entry.path)
                removed += 1
            except OSError:
                logger.exception("Could not remove orphaned file %s", entry.path)
    return removed


@celery_app.task(name="process_media_asset")
def process_media_asset(asset_id: str):
    """
    Background worker that hashes, thumbnails, and generates blurhash arrays.
    """
    parsed_asset_id = uuid.UUID(asset_id)
    db = SessionLocal()
    lock_acquired = False
    try:
        lock_acquired = _acquire_media_lock(db, parsed_asset_id)
        if not lock_acquired:
            return "Asset is already processing"
        if not _claim_media_asset(db, parsed_asset_id):
            return "Asset is not pending or recoverable"

        asset = db.get(MediaAsset, parsed_asset_id)
        if not asset:
            return "Asset not found"

        # Ignore an original_path that escapes the managed directories: a
        # restored archive supplies it verbatim and it is fed to Pillow/ffmpeg.
        from app.services.media_storage import is_managed_media_path

        file_path = (
            asset.original_path
            if is_managed_media_path(asset.original_path)
            else os.path.join(ORIGINALS_PATH, f"{asset.id}.bin")
        )
        if not os.path.exists(file_path):
            asset.processing_state = MediaProcessingState.FAILED
            asset.error_message = f"Original file not found: {file_path}"
            db.commit()
            return asset.error_message

        os.makedirs(DERIVATIVES_PATH, exist_ok=True)
        
        # Image processing
        if asset.kind == MediaKind.PHOTO:
            try:
                with Image.open(file_path) as img:
                    # Fix orientation and extract GPS from EXIF
                    exif = img.getexif()
                    if exif:
                        orientation = exif.get(274)
                        if orientation == 3:
                            img = img.rotate(180, expand=True)
                        elif orientation == 6:
                            img = img.rotate(270, expand=True)
                        elif orientation == 8:
                            img = img.rotate(90, expand=True)

                        gps_info = exif.get_ifd(0x8825)  # GPSInfo IFD
                        if gps_info:
                            try:
                                lat = _dms_to_decimal(gps_info.get(2), gps_info.get(1))
                                lon = _dms_to_decimal(gps_info.get(4), gps_info.get(3))
                                if lat is not None and lon is not None:
                                    asset.gps_location = f"POINT({lon} {lat})"
                            except Exception:
                                pass

                    asset.width = img.width
                    asset.height = img.height
                    asset.aspect_ratio = round(img.width / img.height, 4) if img.height > 0 else 1.0

                    # Full-size derivatives at max 1400px
                    full = img.copy()
                    full.thumbnail((1400, 1400), Image.Resampling.LANCZOS)

                    tmp_webp = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp.webp")
                    tmp_avif = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp.avif")
                    full.save(tmp_webp, format="WEBP", quality=80)
                    full.save(tmp_avif, quality=70)

                    _, webp_url = _immutable_derivative(tmp_webp, asset.id, "webp", "webp")
                    _, avif_url = _immutable_derivative(tmp_avif, asset.id, "avif", "avif")

                    derivative_paths: dict[str, str] = {
                        "webp": webp_url,
                        "avif": avif_url,
                    }

                    # Small variant at max 768px — only when the original exceeds that size
                    if img.width > 768 or img.height > 768:
                        sm = img.copy()
                        sm.thumbnail((768, 768), Image.Resampling.LANCZOS)
                        tmp_sm = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp_sm.webp")
                        sm.save(tmp_sm, format="WEBP", quality=80)
                        _, sm_url = _immutable_derivative(tmp_sm, asset.id, "webp_sm", "webp")
                        derivative_paths["webp_sm"] = sm_url

                    # Dominant color from the already-thumbnailed full copy
                    full.thumbnail((1, 1))
                    color = full.getpixel((0, 0))
                    if isinstance(color, int):
                        asset.dominant_color = f"#{color:06x}"
                    else:
                        asset.dominant_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"

                    # Blurhash from original — blurhash.encode closes the image object
                    img.thumbnail((32, 32))
                    asset.blurhash = blurhash.encode(img, x_components=4, y_components=3)

                    asset.derivative_paths = derivative_paths
                    asset.processing_state = MediaProcessingState.READY
                    asset.error_message = None
            except Exception as e:
                asset.error_message = f"Image processing failed: {e}"
                logger.exception("Image processing failed for media asset %s", asset.id)
                asset.processing_state = MediaProcessingState.FAILED

        # Video processing
        elif asset.kind == MediaKind.VIDEO:
            try:
                # Get duration using ffprobe
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
                duration_str = subprocess.check_output(
                    probe_cmd, timeout=FFPROBE_TIMEOUT_SECONDS
                ).decode('utf-8').strip()
                asset.duration_seconds = float(duration_str)

                # Extract poster image
                tmp_poster = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp-poster.jpg")
                ffmpeg_cmd = ["ffmpeg", "-y", "-i", file_path, "-map", "0:v:0", "-frames:v", "1", "-update", "1", "-q:v", "2", tmp_poster]
                subprocess.run(ffmpeg_cmd, check=True, timeout=FFMPEG_TIMEOUT_SECONDS)

                # Transcode to H.264/AAC MP4 for universal browser compatibility.
                # iPhone HEVC (.mov) originals won't play in Safari's <video> tag,
                # so we always produce a web-safe derivative.
                tmp_mp4 = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp.mp4")
                _transcode_video_to_mp4(file_path, tmp_mp4)
                _assert_transcode_complete(file_path, tmp_mp4)

                # Probe dimensions from the transcoded file so rotation is
                # already baked in and width/height match what the browser sees.
                w, h = _probe_video_dimensions(tmp_mp4)
                asset.width = w
                asset.height = h
                asset.aspect_ratio = round(w / h, 4)

                # Blurhash the poster
                with Image.open(tmp_poster) as img:
                    img.thumbnail((32, 32))
                    asset.blurhash = blurhash.encode(img, x_components=4, y_components=3)

                _, poster_url = _immutable_derivative(tmp_poster, asset.id, "poster", "jpg")
                _, mp4_url = _immutable_derivative(tmp_mp4, asset.id, "mp4", "mp4")

                asset.derivative_paths = {
                    "poster": poster_url,
                    "mp4": mp4_url,
                }
                asset.processing_state = MediaProcessingState.READY
                asset.error_message = None

            except Exception as e:
                asset.error_message = f"Video processing failed: {e}"
                logger.exception("Video processing failed for media asset %s", asset.id)
                asset.processing_state = MediaProcessingState.FAILED

        db.commit()
        delete_original_after_success(asset)
    finally:
        if lock_acquired:
            try:
                _release_media_lock(db, parsed_asset_id)
            except Exception:
                logger.exception("Could not release processing lock for asset %s", parsed_asset_id)
        db.close()


@celery_app.task(name="send_admin_emails")
def send_admin_emails(recipients: list[str], subject: str, text: str, html: str):
    """Deliver an already-rendered admin notification.

    The content is rendered by the caller rather than re-derived here: the
    registration hook runs before the approval state is committed, so a worker
    reading the row back could describe the account incorrectly.
    """
    sent = 0
    for address in recipients:
        try:
            send_email(address, subject, text, html)
            sent += 1
        except Exception:
            logger.exception("Failed to send admin notification to %s", address)
    return f"Sent {sent}/{len(recipients)}"


@celery_app.task(name="dispatch_post_notification")
def dispatch_post_notification(post_id: str):
    db = SessionLocal()
    try:
        logger.info("[notify] dispatch_post_notification started for post %s", post_id)
        post = db.get(Post, uuid.UUID(post_id))
        if not post or not _post_is_published(post):
            logger.warning("[notify] Post %s not found or not published — skipping", post_id)
            return "Post is not published"

        post.trip
        post.stop
        subject, text, html = _post_email_bodies(post, db)
        recipients = _approved_notification_users(db, NotificationFrequency.ALL_UPDATES)
        logger.info("[notify] Found %d approved ALL_UPDATES subscriber(s) for post %s", len(recipients), post_id)
        sent_count = 0
        for user, _preference in recipients:
            kind = f"post_immediate:{post.id}"
            if _notification_already_logged(db, user.id, kind):
                logger.info("[notify] Skipping user %s — already notified", user.id)
                continue
            sent = send_email(user.email, subject, text, html)
            _record_notification(
                db,
                user.id,
                kind,
                {"post_id": str(post.id), "frequency": NotificationFrequency.ALL_UPDATES.value},
                sent,
                None if sent else "SMTP not configured or send failed",
            )
            if sent:
                sent_count += 1
        db.commit()
        logger.info("[notify] dispatch_post_notification complete: sent %d email(s) for post %s", sent_count, post_id)
        return f"Sent {sent_count} immediate post notifications"
    finally:
        db.close()

@celery_app.task(name="dispatch_comment_notification")
def dispatch_comment_notification(comment_id: str):
    from app.models.system import Comment
    db = SessionLocal()
    try:
        comment = db.get(Comment, uuid.UUID(comment_id))
        if not comment:
            return "Comment not found"

        author = db.get(User, comment.author_id)
        author_name = (author.display_name if author else None) or "Someone"
        author_id = comment.author_id

        # Resolve target label
        if comment.target_kind == "post":
            target = db.get(Post, comment.target_id)
            target_label = target.title if target else str(comment.target_id)
            target_url = _post_url(target) if target else _base_url()
        elif comment.target_kind == "stop":
            target = db.get(Stop, comment.target_id)
            target_label = (target.place_name or target.title) if target else str(comment.target_id)
            target_url = _base_url()
        else:
            target_label = f"{comment.target_kind} {comment.target_id}"
            target_url = _base_url()

        subject = f'New comment on "{target_label}"'
        text = (
            f'{author_name} commented on "{target_label}":\n\n'
            f"{comment.body}\n\n"
            f"View: {target_url}\n"
        )
        html = (
            f"<p><strong>{escape(author_name)}</strong> commented on "
            f'<a href="{target_url}">{escape(target_label)}</a>:</p>'
            f"<blockquote>{escape(comment.body)}</blockquote>"
        )

        admins = db.execute(
            select(User).where(
                User.is_active.is_(True),
                User.role == UserRole.ADMIN,
            )
        ).scalars().all()

        # Everyone who has previously commented on this same target should be
        # kept in the loop on each subsequent comment (thread participants).
        prior_author_ids = db.execute(
            select(Comment.author_id)
            .where(
                Comment.target_kind == comment.target_kind,
                Comment.target_id == comment.target_id,
                Comment.deleted_at.is_(None),
                Comment.id != comment.id,
            )
            .distinct()
        ).scalars().all()
        prior_commenters = (
            db.execute(
                select(User).where(
                    User.is_active.is_(True),
                    User.id.in_(prior_author_ids),
                )
            ).scalars().all()
            if prior_author_ids
            else []
        )

        # Dedup by user id and never notify the comment's own author.
        recipients: dict[uuid.UUID, User] = {}
        for recipient in (*admins, *prior_commenters):
            if recipient.id == author_id:
                continue
            recipients[recipient.id] = recipient

        for recipient in recipients.values():
            send_email(recipient.email, subject, text, html)
        return f"Notified {len(recipients)} recipient(s) of comment {comment_id}"
    finally:
        db.close()


@celery_app.task(name="dispatch_like_notification")
def dispatch_like_notification(like_id: str):
    """Notify a comment's author when their comment is liked."""
    from app.models.system import Comment, Like
    db = SessionLocal()
    try:
        like = db.get(Like, uuid.UUID(like_id))
        if not like:
            return "Like not found"

        # Only comment likes notify an author today; other targets are admin-owned.
        if like.target_kind != "comment":
            return "No notification for this like target"

        comment = db.get(Comment, like.target_id)
        if not comment or comment.deleted_at is not None:
            return "Comment not found"
        if comment.author_id == like.author_id:
            return "Self-like; no notification"

        author = db.get(User, comment.author_id)
        if not author or not author.is_active:
            return "Comment author unavailable"

        liker = db.get(User, like.author_id)
        liker_name = (liker.display_name if liker else None) or "Someone"

        target_url = _base_url()
        if comment.target_kind == "post":
            target = db.get(Post, comment.target_id)
            if target:
                target_url = _post_url(target)

        subject = "Someone liked your comment"
        text = (
            f"{liker_name} liked your comment:\n\n"
            f"{comment.body}\n\n"
            f"View: {target_url}\n"
        )
        html = (
            f"<p><strong>{escape(liker_name)}</strong> liked your comment:</p>"
            f"<blockquote>{escape(comment.body)}</blockquote>"
            f'<p><a href="{target_url}">View</a></p>'
        )

        send_email(author.email, subject, text, html)
        return f"Notified comment author of like {like_id}"
    finally:
        db.close()


@celery_app.task(name="create_db_backup")
def create_db_backup():
    """Write a timestamped pg_dump to the backups dir and prune old ones.

    The dump is DB-only; media is backed up at the filesystem level. Operators
    rsync the backups dir alongside derivatives for disaster recovery.
    """
    from app.services.db_backup import create_db_dump, prune_old_dumps

    keep = int(os.getenv("BACKUP_RETENTION", "7"))
    path = create_db_dump()
    removed = prune_old_dumps(keep=keep)
    logger.info("DB backup written to %s (pruned %d old dump(s), keeping %d)", path, removed, keep)
    return path


@celery_app.task(name="refresh_weather")
def refresh_weather():
    """Fetch weather for the current stop and cache it in Redis.

    Runs hourly so public page renders (/api/home) never make a blocking
    external weather call. Coordinates come from the coords key published by
    /api/home; if that's unset (e.g. nobody has hit the homepage since boot),
    fall back to querying the current stop directly.
    """
    import redis
    from geoalchemy2 import Geometry
    from sqlalchemy import cast, func

    from app.services.weather import (
        WEATHER_COORDS_KEY,
        WEATHER_TTL_SECONDS,
        fetch_weather,
        weather_cache_key,
    )

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    lat = lon = None
    coords = client.get(WEATHER_COORDS_KEY)
    if coords:
        try:
            lat_s, lon_s = coords.split(",", 1)
            lat, lon = float(lat_s), float(lon_s)
        except ValueError:
            lat = lon = None

    if lat is None or lon is None:
        db = SessionLocal()
        try:
            point = cast(Stop.location, Geometry(geometry_type="POINT", srid=4326))
            row = db.execute(
                select(func.ST_Y(point), func.ST_X(point))
                .where(
                    Stop.status == StopStatus.PUBLISHED,
                    Stop.visibility == Visibility.PUBLIC,
                )
                .order_by(Stop.is_current.desc(), Stop.start_date.desc())
                .limit(1)
            ).first()
        finally:
            db.close()
        if not row:
            logger.info("[weather] No current stop found; skipping refresh")
            return "No current stop"
        lat, lon = float(row[0]), float(row[1])

    data = fetch_weather(lat, lon)
    if not data:
        logger.warning("[weather] Fetch returned no data for %s,%s", lat, lon)
        return "Fetch failed"

    client.set(weather_cache_key(), json.dumps(data), ex=WEATHER_TTL_SECONDS)
    logger.info("[weather] Cached weather for %s,%s", lat, lon)
    return f"Cached weather for {lat},{lon}"


@celery_app.task(name="dispatch_weekly_digest")
def dispatch_weekly_digest():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=7)
        posts = (
            db.execute(
                select(Post)
                .where(
                    Post.status == PostStatus.PUBLISHED,
                    Post.posted_at >= since,
                    Post.posted_at < now,
                )
                .order_by(Post.posted_at.asc())
            )
            .scalars()
            .all()
        )
        if not posts:
            logger.info("[digest] No public posts found for weekly digest window")
            return "No posts"

        for post in posts:
            post.trip
            post.stop

        kind = f"weekly_digest:{since.date().isoformat()}:{now.date().isoformat()}"
        sent_count = 0
        for user, _preference in _approved_notification_users(db, NotificationFrequency.WEEKLY_DIGEST):
            if _notification_already_logged(db, user.id, kind):
                continue
            subject = "Your weekly Postmarked update"
            lines = ["Here are this week's Postmarked updates:", ""]
            html_items = []
            for post in posts:
                url = _post_url(post)
                lines.append(f"- {post.title}: {url}")
                html_items.append(f'<li><a href="{url}">{escape(post.title)}</a></li>')
            sent = send_email(
                user.email,
                subject,
                "\n".join(lines) + "\n",
                f"<p>Here are this week's Postmarked updates:</p><ul>{''.join(html_items)}</ul>",
            )
            _record_notification(
                db,
                user.id,
                kind,
                {
                    "post_ids": [str(post.id) for post in posts],
                    "frequency": NotificationFrequency.WEEKLY_DIGEST.value,
                    "since": since.isoformat(),
                    "until": now.isoformat(),
                },
                sent,
                None if sent else "SMTP not configured or send failed",
            )
            if sent:
                sent_count += 1
        db.commit()
        return f"Sent {sent_count} weekly digests"
    finally:
        db.close()

@celery_app.task(name="sweep_stale_media")
def sweep_stale_media():
    """Requeue assets stuck in PENDING and remove orphaned upload artifacts.

    Covers three ways work goes missing: a broker outage at upload time, a
    worker killed mid-task, and tus uploads or derivative temp files abandoned
    with no row referencing them.
    """
    now = datetime.now(timezone.utc)
    pending_cutoff = now - timedelta(seconds=MEDIA_PENDING_REQUEUE_SECONDS)
    processing_cutoff = now - timedelta(seconds=MEDIA_PROCESSING_LEASE_SECONDS)
    requeued = 0
    db = SessionLocal()
    try:
        stale = db.execute(
            select(MediaAsset).where(
                or_(
                    and_(
                        MediaAsset.processing_state == MediaProcessingState.PENDING,
                        MediaAsset.updated_at < pending_cutoff,
                    ),
                    and_(
                        MediaAsset.processing_state == MediaProcessingState.PROCESSING,
                        MediaAsset.updated_at < processing_cutoff,
                    ),
                )
            )
        ).scalars().all()
        for asset in stale:
            try:
                process_media_asset.delay(str(asset.id))
                requeued += 1
            except Exception:
                logger.exception("Could not requeue stale asset %s", asset.id)

        known = {str(row[0]) for row in db.execute(select(MediaAsset.id)).all()}
    finally:
        db.close()

    removed = _remove_stale_upload_artifacts(known, now=now)
    cutoff_ts = pending_cutoff.timestamp()
    if os.path.isdir(DERIVATIVES_PATH):
        for entry in os.scandir(DERIVATIVES_PATH):
            if not entry.is_file() or ".tmp" not in entry.name:
                continue
            stem = entry.name.split(".", 1)[0]
            if stem in known:
                continue
            try:
                if entry.stat().st_mtime < cutoff_ts:
                    os.remove(entry.path)
                    removed += 1
            except OSError:
                logger.exception("Could not remove orphaned file %s", entry.path)

    return f"Requeued {requeued} pending assets, removed {removed} orphaned files"

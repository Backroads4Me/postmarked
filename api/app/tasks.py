import hashlib
import os
import shutil
import uuid
import logging
import json
from html import escape
from celery import Celery
from celery.schedules import crontab
import subprocess
from datetime import datetime, timedelta, timezone
from PIL import Image, ExifTags
import blurhash
from pillow_heif import register_heif_opener

register_heif_opener()
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.content import MediaAsset, Post, SiteTextSection
from app.models.enums import ApprovalState, MediaKind, MediaProcessingState, NotificationFrequency, PostStatus, Visibility
from app.models.system import NotificationLog
from app.models.user import NotificationPreference, User
from app.services.mailer import send_email

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
_DATABASE_URL_RAW = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/postmarked")
DATABASE_URL_SYNC = _DATABASE_URL_RAW.replace("postgresql://", "postgresql+psycopg://", 1)

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/tmp/originals")
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/tmp/derivatives")

celery_app = Celery("postmarked_tasks", broker=REDIS_URL)
celery_app.conf.timezone = os.getenv("CELERY_TIMEZONE", "UTC")
celery_app.conf.beat_schedule = {
    "weekly-digest-monday-morning": {
        "task": "dispatch_weekly_digest",
        "schedule": crontab(hour=8, minute=0, day_of_week="monday"),
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
                User.is_active == True,
                User.approval_state == ApprovalState.APPROVED,
                NotificationPreference.email_opted_in == True,
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


def _post_email_bodies(post: Post, db) -> tuple[str, str, str]:
    url = _post_url(post)
    body = post.body or ""

    config = db.execute(
        select(SiteTextSection).where(
            SiteTextSection.page_key == "email",
            SiteTextSection.section_key == "post_notification",
        )
    ).scalar_one_or_none()

    default_subject = "New update from the road"
    default_cta = "See the photos"

    if config:
        subject = (config.heading or default_subject).format(post_title=post.title)
        intro = (config.body or "").format(post_title=post.title) if config.body else None
        cta = config.cta_label or default_cta
    else:
        subject = default_subject
        intro = None
        cta = default_cta

    if intro:
        text = f"{intro}\n\n{post.title}\n\n{body}\n\n{cta}: {url}\n"
        html = (
            f"<p>{escape(intro)}</p>"
            f"<h1>{escape(post.title)}</h1>"
            f"<p>{escape(body)}</p>"
            f'<p><a href="{url}">{escape(cta)}</a></p>'
        )
    else:
        text = f"{post.title}\n\n{body}\n\n{cta}: {url}\n"
        html = (
            f"<h1>{escape(post.title)}</h1>"
            f"<p>{escape(body)}</p>"
            f'<p><a href="{url}">{escape(cta)}</a></p>'
        )

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
    raw = subprocess.check_output(dim_cmd).decode("utf-8")
    data = json.loads(raw or "{}")
    for stream in data.get("streams", []):
        width = stream.get("width")
        height = stream.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return width, height
    raise ValueError("No video stream with numeric width and height found")


def _transcode_video_to_mp4(file_path: str, mp4_path: str) -> None:
    """Create an iOS/Safari-friendly H.264/AAC MP4 derivative."""
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
    ], check=True)


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


@celery_app.task(name="process_media_asset")
def process_media_asset(asset_id: str):
    """
    Background worker that hashes, thumbnails, and generates blurhash arrays.
    """
    db = SessionLocal()
    try:
        asset = db.get(MediaAsset, uuid.UUID(asset_id))
        if not asset:
            return "Asset not found"

        file_path = asset.original_path or os.path.join(ORIGINALS_PATH, f"{asset.id}.bin")
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
                        if orientation == 3:   img = img.rotate(180, expand=True)
                        elif orientation == 6: img = img.rotate(270, expand=True)
                        elif orientation == 8: img = img.rotate(90, expand=True)

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
                duration_str = subprocess.check_output(probe_cmd).decode('utf-8').strip()
                asset.duration_seconds = float(duration_str)

                # Extract poster image
                tmp_poster = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp-poster.jpg")
                ffmpeg_cmd = ["ffmpeg", "-y", "-i", file_path, "-vframes", "1", "-q:v", "2", tmp_poster]
                subprocess.run(ffmpeg_cmd, check=True)

                # Transcode to H.264/AAC MP4 for universal browser compatibility.
                # iPhone HEVC (.mov) originals won't play in Safari's <video> tag,
                # so we always produce a web-safe derivative.
                tmp_mp4 = os.path.join(DERIVATIVES_PATH, f"{asset.id}.tmp.mp4")
                _transcode_video_to_mp4(file_path, tmp_mp4)

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
    finally:
        db.close()


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

INGEST_PATH = os.getenv("INGEST_PATH", "/tmp/ingest")
PROCESSED_INGEST_PATH = os.path.join(INGEST_PATH, "processed")
os.makedirs(INGEST_PATH, exist_ok=True)

def hash_file(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def _processed_ingest_path(filepath: str) -> str:
    rel_path = os.path.relpath(filepath, INGEST_PATH)
    dest_path = os.path.join(PROCESSED_INGEST_PATH, rel_path)
    base, ext = os.path.splitext(dest_path)
    candidate = dest_path
    counter = 1
    while os.path.exists(candidate):
        candidate = f"{base}-{counter}{ext}"
        counter += 1
    os.makedirs(os.path.dirname(candidate), exist_ok=True)
    return candidate


def _move_to_processed(filepath: str) -> str:
    dest_path = _processed_ingest_path(filepath)
    shutil.move(filepath, dest_path)
    return dest_path


@celery_app.task(name="scan_filesystem")
def scan_filesystem():
    """
    Recursively scans INGEST_PATH for new media files and hashes them. 
    If unique, it copies them to ORIGINALS_PATH and fires processing logic.
    Handled files are moved to INGEST_PATH/processed so ingest stays a queue.
    """
    db = SessionLocal()
    try:
        if not os.path.exists(INGEST_PATH):
            return "Ingest path missing"
            
        for root, dirs, files in os.walk(INGEST_PATH):
            if os.path.commonpath([PROCESSED_INGEST_PATH, root]) == PROCESSED_INGEST_PATH:
                continue
            for file in files:
                if file.startswith('.'): continue
                
                filepath = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext not in ['.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov']:
                    continue
                
                fhash = hash_file(filepath)
                
                # Check DB mapping
                query = select(MediaAsset).where(MediaAsset.original_sha256 == fhash)
                existing = db.execute(query).scalar_one_or_none()
                if existing:
                    _move_to_processed(filepath)
                    continue # Skip deduplicated
                
                # Register new asset
                new_id = uuid.uuid4()
                dest_path = os.path.join(ORIGINALS_PATH, f"{new_id}.bin")
                shutil.copy2(filepath, dest_path)
                
                # Write to DB
                kind = MediaKind.VIDEO if file_ext in ['.mp4', '.mov'] else MediaKind.PHOTO
                asset = MediaAsset(
                    id=new_id,
                    kind=kind,
                    original_path=dest_path,
                    original_sha256=fhash,
                    original_filename=file,
                    original_size_bytes=os.path.getsize(dest_path),
                    mime_type=(
                        "video/quicktime" if file_ext == ".mov"
                        else "video/mp4" if kind == MediaKind.VIDEO
                        else "image/png" if file_ext == ".png"
                        else "image/webp" if file_ext == ".webp"
                        else "image/jpeg"
                    ),
                    visibility=Visibility.PRIVATE, # Private until manually assigned by admin
                    processing_state=MediaProcessingState.PENDING,
                    featured=False,
                    sort_order=0,
                )
                db.add(asset)
                try:
                    db.commit()
                except IntegrityError:
                    # Another worker raced and inserted the same SHA-256 first.
                    db.rollback()
                    _move_to_processed(filepath)
                    continue
                _move_to_processed(filepath)

                # Delegate
                process_media_asset.delay(str(new_id))
    finally:
        db.close()

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

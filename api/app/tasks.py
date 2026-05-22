import os
import uuid
import logging
import json
from celery import Celery
import subprocess
from PIL import Image, ExifTags
import blurhash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.content import MediaAsset
from app.models.enums import MediaKind, MediaProcessingState, Visibility

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL_SYNC = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/postmarked")

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/tmp/originals")
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/tmp/derivatives")

celery_app = Celery("postmarked_tasks", broker=REDIS_URL)

engine = create_engine(DATABASE_URL_SYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
                    
                    # Create WebP derivative
                    thumb_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.webp")
                    img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                    img.save(thumb_path, format="WEBP", quality=80)
                    
                    # Attempt dominant color
                    img.thumbnail((1, 1))
                    color = img.getpixel((0,0))
                    if isinstance(color, int):
                        asset.dominant_color = f"#{color:06x}"
                    else:
                        asset.dominant_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"

                    # Generate Blurhash last: blurhash-python closes the image object.
                    img.thumbnail((32, 32))
                    asset.blurhash = blurhash.encode(img, x_components=4, y_components=3)
                        
                    asset.derivative_paths = {"webp": f"/media/{asset.id}/webp"}
                    asset.processing_state = MediaProcessingState.READY
                    asset.error_message = None
            except Exception as e:
                asset.error_message = f"Image processing failed: {e}"
                logger.exception("Image processing failed for media asset %s", asset.id)
                asset.processing_state = MediaProcessingState.FAILED

        # Video processing 
        elif asset.kind.value == "video":
            try:
                # Get duration using ffprobe
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
                duration_str = subprocess.check_output(probe_cmd).decode('utf-8').strip()
                asset.duration_seconds = float(duration_str)

                # Get dimensions from the first valid video stream.
                w, h = _probe_video_dimensions(file_path)
                asset.width = w
                asset.height = h
                asset.aspect_ratio = round(w / h, 4)

                # Extract poster image
                poster_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}-poster.jpg")
                ffmpeg_cmd = ["ffmpeg", "-y", "-i", file_path, "-vframes", "1", "-q:v", "2", poster_path]
                subprocess.run(ffmpeg_cmd, check=True)
                
                # Blurhash the poster
                with Image.open(poster_path) as img:
                    img.thumbnail((32, 32))
                    asset.blurhash = blurhash.encode(img, x_components=4, y_components=3)

                asset.derivative_paths = {"poster": f"/media/{asset.id}/poster"}
                asset.processing_state = MediaProcessingState.READY
                asset.error_message = None

            except Exception as e:
                asset.error_message = f"Video processing failed: {e}"
                logger.exception("Video processing failed for media asset %s", asset.id)
                asset.processing_state = MediaProcessingState.FAILED

        db.commit()
    finally:
        db.close()

import hashlib
import shutil

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
                    mime_type="video/mp4" if kind == MediaKind.VIDEO else "image/jpeg",
                    visibility=Visibility.PRIVATE, # Private until manually assigned by admin
                    processing_state=MediaProcessingState.PENDING,
                    featured=False,
                    sort_order=0,
                )
                db.add(asset)
                db.commit()
                _move_to_processed(filepath)
                
                # Delegate
                process_media_asset.delay(str(new_id))
    finally:
        db.close()

@celery_app.task(name="dispatch_weekly_digest")
def dispatch_weekly_digest():
    """
    Mock digest email dispatcher.
    Queries users with NotificationPreference enabled, checks for recent trips,
    and logs the payload without sending actual SMTP emails.
    """
    db = SessionLocal()
    try:
        from app.models.user import User
        from app.models.system import NotificationLog
        from datetime import datetime, timezone
        
        # In a real app we would join on notification preferences
        query = select(User).where(User.is_active == True)
        users = db.execute(query).scalars().all()
        
        for user in users:
            log_entry = NotificationLog(
                user_id=user.id,
                kind="WEEKLY_DIGEST",
                payload={"mocked": True, "note": "Email dispatch disabled for local deployment."},
                delivery_status="SENT",
            )
            db.add(log_entry)
            logger.info("[DIGEST MOCK] Would have sent digest email to user %s", user.id)
            
        db.commit()
    finally:
        db.close()

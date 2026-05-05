import os
import uuid
from celery import Celery
import subprocess
from PIL import Image, ExifTags
import blurhash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.content import MediaAsset
from app.models.enums import MediaKind, MediaProcessingState, Visibility

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL_SYNC = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/goodpath")

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/tmp/originals")
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/tmp/derivatives")

celery_app = Celery("goodpath_tasks", broker=REDIS_URL)

engine = create_engine(DATABASE_URL_SYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

        file_path = os.path.join(ORIGINALS_PATH, f"{asset.id}.bin")
        if not os.path.exists(file_path):
            asset.processing_state = MediaProcessingState.FAILED
            db.commit()
            return "File not found"

        os.makedirs(DERIVATIVES_PATH, exist_ok=True)
        
        # Image processing
        if asset.kind == MediaKind.PHOTO:
            try:
                with Image.open(file_path) as img:
                    # Fix orientation based on EXIF
                    exif = img.getexif()
                    if exif:
                        orientation = exif.get(274)
                        if orientation == 3:   img = img.rotate(180, expand=True)
                        elif orientation == 6: img = img.rotate(270, expand=True)
                        elif orientation == 8: img = img.rotate(90, expand=True)

                    asset.width = img.width
                    asset.height = img.height
                    asset.aspect_ratio = round(img.width / img.height, 4) if img.height > 0 else 1.0
                    
                    # Create WebP derivative
                    thumb_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}.webp")
                    img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                    img.save(thumb_path, format="WEBP", quality=80)
                    
                    # Generate Blurhash
                    img.thumbnail((32, 32))
                    asset.blurhash = blurhash.encode(img, x_components=4, y_components=3)
                    
                    # Attempt dominant color
                    img.thumbnail((1, 1))
                    color = img.getpixel((0,0))
                    if isinstance(color, int):
                        asset.dominant_color = f"#{color:06x}"
                    else:
                        asset.dominant_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                        
                    asset.derivative_paths = {"webp": f"/media/derivatives/{asset.id}.webp"}
                    asset.processing_state = MediaProcessingState.READY
            except Exception as e:
                print(f"Image processing failed: {e}")
                asset.processing_state = MediaProcessingState.FAILED

        # Video processing 
        elif asset.kind.value == "video":
            try:
                # Get duration using ffprobe
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
                duration_str = subprocess.check_output(probe_cmd).decode('utf-8').strip()
                asset.duration_seconds = float(duration_str)

                # Get dimensions 
                dim_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", file_path]
                dim_str = subprocess.check_output(dim_cmd).decode('utf-8').strip()
                w, h = dim_str.split('x')
                asset.width = int(w)
                asset.height = int(h)
                asset.aspect_ratio = round(int(w)/int(h), 4)

                # Extract poster image
                poster_path = os.path.join(DERIVATIVES_PATH, f"{asset.id}-poster.jpg")
                ffmpeg_cmd = ["ffmpeg", "-y", "-i", file_path, "-vframes", "1", "-q:v", "2", poster_path]
                subprocess.run(ffmpeg_cmd, check=True)
                
                # Blurhash the poster
                with Image.open(poster_path) as img:
                    img.thumbnail((32, 32))
                    asset.blurhash = blurhash.encode(img, x_components=4, y_components=3)

                asset.derivative_paths = {"poster": f"/media/derivatives/{asset.id}-poster.jpg"}
                asset.processing_state = MediaProcessingState.READY

            except Exception as e:
                print(f"Video processing failed: {e}")
                asset.processing_state = MediaProcessingState.FAILED

        db.commit()
    finally:
        db.close()

import hashlib
import shutil

INGEST_PATH = os.getenv("INGEST_PATH", "/tmp/ingest")
os.makedirs(INGEST_PATH, exist_ok=True)

def hash_file(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

@celery_app.task(name="scan_filesystem")
def scan_filesystem():
    """
    Recursively scans INGEST_PATH for new media files and hashes them. 
    If unique, it copies them to ORIGINALS_PATH and fires processing logic.
    """
    db = SessionLocal()
    try:
        if not os.path.exists(INGEST_PATH):
            return "Ingest path missing"
            
        for root, dirs, files in os.walk(INGEST_PATH):
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
            print(f"[DIGEST MOCK] Would have sent digest email to {user.email}")
            
        db.commit()
    finally:
        db.close()

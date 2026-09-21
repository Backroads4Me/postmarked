import uuid
from datetime import datetime

from app.models.enums import MediaKind, MediaProcessingState, Visibility
from app.schemas.common import BaseResponse


class MediaAssetBase(BaseResponse):
    id: uuid.UUID
    kind: MediaKind
    processing_state: MediaProcessingState
    error_message: str | None = None

    width: int | None = None
    height: int | None = None
    aspect_ratio: float | None = None
    duration_seconds: float | None = None
    dominant_color: str | None = None
    blurhash: str | None = None

    caption: str | None = None
    alt_text: str | None = None
    visibility: Visibility

    derivative_paths: dict | None = {}
    featured: bool
    sort_order: int

    original_filename: str | None = None
    created_at: datetime

    stop_id: uuid.UUID | None = None
    post_id: uuid.UUID | None = None
    trip_id: uuid.UUID | None = None

class MediaAssetOut(MediaAssetBase):
    pass

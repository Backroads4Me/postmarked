import uuid
from typing import Optional
from datetime import datetime
from pydantic import Field

from app.schemas.common import BaseResponse, GeoJsonPoint
from app.models.enums import MediaKind, MediaProcessingState, Visibility

class MediaAssetBase(BaseResponse):
    id: uuid.UUID
    kind: MediaKind
    processing_state: MediaProcessingState
    error_message: Optional[str] = None
    
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[float] = None
    duration_seconds: Optional[float] = None
    dominant_color: Optional[str] = None
    blurhash: Optional[str] = None
    
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    visibility: Visibility
    
    derivative_paths: Optional[dict] = dict()
    featured: bool
    sort_order: int
    
class MediaAssetOut(MediaAssetBase):
    pass

"""
Schemas for Post (quick updates).
"""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut


class PostOut(BaseResponse):
    id: uuid.UUID
    title: str
    body: Optional[str] = None
    slug: str
    posted_at: datetime
    visibility: str
    stop_id: Optional[uuid.UUID] = None
    trip_id: Optional[uuid.UUID] = None

    # Denormalized for display
    stop_title: Optional[str] = None
    trip_title: Optional[str] = None
    place_name: Optional[str] = None

    media: List[MediaAssetOut] = []


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=10000)
    stop_id: Optional[uuid.UUID] = None
    trip_id: Optional[uuid.UUID] = None
    visibility: str = "public"
    posted_at: Optional[datetime] = None
    # IDs of MediaAsset rows to attach (from a prior TUS upload).
    media_ids: List[uuid.UUID] = Field(default_factory=list)


class PostUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=10000)
    stop_id: Optional[uuid.UUID] = None
    visibility: Optional[str] = None

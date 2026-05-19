"""
Schemas for Post (quick updates and activity posts).
"""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ActivityType, PostStatus, PostType
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut
from app.schemas.poi import POIOut


class PostOut(BaseResponse):
    id: uuid.UUID
    title: str
    body: Optional[str] = None
    slug: str
    posted_at: datetime
    visibility: str
    status: PostStatus = PostStatus.DRAFT
    stop_id: Optional[uuid.UUID] = None
    trip_id: Optional[uuid.UUID] = None

    # Denormalized for display
    stop_title: Optional[str] = None
    trip_title: Optional[str] = None
    place_name: Optional[str] = None

    post_type: PostType = PostType.UPDATE
    activity_type: Optional[ActivityType] = None
    summary: Optional[str] = None
    activity_started_at: Optional[datetime] = None
    activity_ended_at: Optional[datetime] = None
    poi_id: Optional[uuid.UUID] = None
    poi: Optional[POIOut] = None

    media: List[MediaAssetOut] = []


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=10000)
    stop_id: Optional[uuid.UUID] = None
    trip_id: Optional[uuid.UUID] = None
    visibility: str = "private"
    status: PostStatus = PostStatus.DRAFT
    posted_at: Optional[datetime] = None
    # IDs of MediaAsset rows to attach (from a prior TUS upload).
    media_ids: List[uuid.UUID] = Field(default_factory=list)

    post_type: PostType = PostType.UPDATE
    activity_type: Optional[ActivityType] = None
    summary: Optional[str] = Field(default=None, max_length=500)
    activity_started_at: Optional[datetime] = None
    activity_ended_at: Optional[datetime] = None
    poi_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def activity_requires_started_at(self) -> "PostCreate":
        if self.post_type == PostType.ACTIVITY and self.activity_started_at is None:
            raise ValueError("activity_started_at is required for activity posts")
        return self


class PostUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=10000)
    stop_id: Optional[uuid.UUID] = None
    visibility: Optional[str] = None
    status: Optional[PostStatus] = None
    posted_at: Optional[datetime] = None

    post_type: Optional[PostType] = None
    activity_type: Optional[ActivityType] = None
    summary: Optional[str] = Field(default=None, max_length=500)
    activity_started_at: Optional[datetime] = None
    activity_ended_at: Optional[datetime] = None
    poi_id: Optional[uuid.UUID] = None

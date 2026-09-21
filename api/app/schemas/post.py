"""
Schemas for Post (quick updates and activity posts).
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ActivityType, PostStatus, PostType
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut
from app.schemas.poi import POIOut


class PostOut(BaseResponse):
    id: uuid.UUID
    title: str
    body: str | None = None
    slug: str
    posted_at: datetime
    visibility: str
    status: PostStatus = PostStatus.DRAFT
    stop_id: uuid.UUID | None = None
    trip_id: uuid.UUID | None = None

    # Denormalized for display
    stop_title: str | None = None
    trip_title: str | None = None
    place_name: str | None = None

    post_type: PostType = PostType.UPDATE
    activity_type: ActivityType | None = None
    summary: str | None = None
    activity_started_at: datetime | None = None
    activity_ended_at: datetime | None = None
    poi_id: uuid.UUID | None = None
    poi: POIOut | None = None

    media: list[MediaAssetOut] = []


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=10000)
    stop_id: uuid.UUID | None = None
    trip_id: uuid.UUID | None = None
    visibility: str = "private"
    status: PostStatus = PostStatus.DRAFT
    posted_at: datetime | None = None
    # IDs of MediaAsset rows to attach (from a prior TUS upload).
    media_ids: list[uuid.UUID] = Field(default_factory=list)

    post_type: PostType = PostType.UPDATE
    activity_type: ActivityType | None = None
    summary: str | None = Field(default=None, max_length=500)
    activity_started_at: datetime | None = None
    activity_ended_at: datetime | None = None
    poi_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def activity_requires_started_at(self) -> "PostCreate":
        if self.post_type == PostType.ACTIVITY and self.activity_started_at is None:
            raise ValueError("activity_started_at is required for activity posts")
        return self


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=10000)
    stop_id: uuid.UUID | None = None
    visibility: str | None = None
    status: PostStatus | None = None
    posted_at: datetime | None = None

    post_type: PostType | None = None
    activity_type: ActivityType | None = None
    summary: str | None = Field(default=None, max_length=500)
    activity_started_at: datetime | None = None
    activity_ended_at: datetime | None = None
    poi_id: uuid.UUID | None = None
    media_ids: list[uuid.UUID] = Field(default_factory=list)

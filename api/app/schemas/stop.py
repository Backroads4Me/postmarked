import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import StopStatus, Visibility
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut


class StopBase(BaseResponse):
    id: uuid.UUID
    trip_id: uuid.UUID
    slug: str
    title: str
    summary: str | None = None

    start_date: datetime
    end_date: datetime | None = None

    status: StopStatus
    visibility: Visibility

    sort_order: int
    is_favorite: bool
    tags: list[str] | None = []

    place_name: str | None = None
    address_label: str | None = None

class StopOut(StopBase):
    cover_media: MediaAssetOut | None = None

class StopCreate(BaseModel):
    trip_id: uuid.UUID
    slug: str
    title: str
    summary: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_date: datetime
    end_date: datetime | None = None
    status: StopStatus = StopStatus.DRAFT
    visibility: Visibility = Visibility.PRIVATE
    sort_order: int = 1
    place_name: str | None = None

class StopUpdate(BaseModel):
    slug: str | None = None
    title: str | None = None
    summary: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: StopStatus | None = None
    visibility: Visibility | None = None
    sort_order: int | None = None
    place_name: str | None = None
    body: str | None = None


class StopBulkUpdate(BaseModel):
    stop_ids: list[uuid.UUID] = Field(min_length=1)
    status: StopStatus | None = None
    visibility: Visibility | None = None
    delete: bool = False

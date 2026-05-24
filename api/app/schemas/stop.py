import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.common import BaseResponse, GeoJsonPoint
from app.schemas.media import MediaAssetOut
from app.models.enums import StopStatus, Visibility

class StopBase(BaseResponse):
    id: uuid.UUID
    trip_id: uuid.UUID
    slug: str
    title: str
    summary: Optional[str] = None

    start_date: datetime
    end_date: Optional[datetime] = None

    status: StopStatus
    visibility: Visibility

    sort_order: int
    is_favorite: bool
    tags: Optional[List[str]] = []

    place_name: Optional[str] = None
    address_label: Optional[str] = None

class StopOut(StopBase):
    cover_media: Optional[MediaAssetOut] = None

class StopDetailOut(StopOut):
    body: Optional[str] = None

class StopCreate(BaseModel):
    trip_id: uuid.UUID
    slug: str
    title: str
    summary: Optional[str] = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_date: datetime
    end_date: Optional[datetime] = None
    status: StopStatus = StopStatus.DRAFT
    visibility: Visibility = Visibility.PRIVATE
    sort_order: int = 1
    place_name: Optional[str] = None

class StopUpdate(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[StopStatus] = None
    visibility: Optional[Visibility] = None
    sort_order: Optional[int] = None
    place_name: Optional[str] = None
    body: Optional[str] = None


class StopBulkUpdate(BaseModel):
    stop_ids: List[uuid.UUID] = Field(min_length=1)
    status: Optional[StopStatus] = None
    visibility: Optional[Visibility] = None
    delete: bool = False

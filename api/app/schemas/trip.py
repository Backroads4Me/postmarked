import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import TripStatus, Visibility
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut
from app.schemas.stop import StopOut


class TripBase(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    summary: str | None = None
    
    start_date: datetime | None = None
    end_date: datetime | None = None
    
    status: TripStatus
    visibility: Visibility
    
    total_distance_meters: float | None = None
    tags: list[str] | None = []

class TripOut(TripBase):
    cover_media: MediaAssetOut | None = None

class TripDetailOut(TripOut):
    body: str | None = None
    stops: list[StopOut] = []

class TripCreate(BaseModel):
    slug: str
    title: str
    summary: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: TripStatus = TripStatus.DRAFT
    visibility: Visibility = Visibility.PRIVATE

class TripUpdate(BaseModel):
    slug: str | None = None
    title: str | None = None
    summary: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: TripStatus | None = None
    visibility: Visibility | None = None
    body: str | None = None
    cover_media_id: uuid.UUID | None = None

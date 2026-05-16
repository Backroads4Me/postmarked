import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.schemas.common import BaseResponse, GeoJsonPolygon, GeoJsonLineString
from app.schemas.media import MediaAssetOut
from app.schemas.stop import StopOut
from app.models.enums import TripStatus, Visibility

class TripBase(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    summary: Optional[str] = None
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    status: TripStatus
    visibility: Visibility
    
    total_distance_meters: Optional[float] = None
    tags: Optional[List[str]] = []

class TripOut(TripBase):
    cover_media: Optional[MediaAssetOut] = None

class TripDetailOut(TripOut):
    body: Optional[str] = None
    stops: List[StopOut] = []

class TripCreate(BaseModel):
    slug: str
    title: str
    summary: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: TripStatus = TripStatus.PLANNED
    visibility: Visibility = Visibility.PUBLIC

class TripUpdate(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[TripStatus] = None
    visibility: Optional[Visibility] = None
    body: Optional[str] = None
    cover_media_id: Optional[uuid.UUID] = None

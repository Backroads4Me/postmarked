import uuid
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import POIType
from app.schemas.common import BaseResponse


class POIOut(BaseResponse):
    id: uuid.UUID
    stop_id: uuid.UUID
    label: str
    poi_type: POIType
    notes: Optional[str] = None
    google_maps_url: Optional[str] = None
    latitude: float
    longitude: float


class POICreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    poi_type: POIType = POIType.OTHER
    notes: Optional[str] = Field(default=None, max_length=2000)
    google_maps_url: Optional[str] = Field(default=None, max_length=500)
    latitude: float
    longitude: float


class POIUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    poi_type: Optional[POIType] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    google_maps_url: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

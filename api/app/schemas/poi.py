import uuid

from pydantic import BaseModel, Field

from app.models.enums import POIType
from app.schemas.common import BaseResponse


class POIOut(BaseResponse):
    id: uuid.UUID
    stop_id: uuid.UUID
    label: str
    poi_type: POIType
    notes: str | None = None
    google_maps_url: str | None = None
    latitude: float
    longitude: float


class POICreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    poi_type: POIType = POIType.OTHER
    notes: str | None = Field(default=None, max_length=2000)
    google_maps_url: str | None = Field(default=None, max_length=500)
    latitude: float
    longitude: float


class POIUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    poi_type: POIType | None = None
    notes: str | None = Field(default=None, max_length=2000)
    google_maps_url: str | None = Field(default=None, max_length=500)
    latitude: float | None = None
    longitude: float | None = None

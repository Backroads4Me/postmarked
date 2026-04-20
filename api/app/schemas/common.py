from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict
import uuid
from app.models.enums import Visibility

class PointCoordinates(BaseModel):
    lon: float
    lat: float

class GeoJsonPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] # [lon, lat]

class GeoJsonPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]

class GeoJsonLineString(BaseModel):
    type: str = "LineString"
    coordinates: List[List[float]]

class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

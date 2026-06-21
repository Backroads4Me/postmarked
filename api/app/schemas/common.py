from typing import List
from pydantic import BaseModel, ConfigDict

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

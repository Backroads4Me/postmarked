
from pydantic import BaseModel, ConfigDict


class GeoJsonPoint(BaseModel):
    type: str = "Point"
    coordinates: list[float] # [lon, lat]

class GeoJsonPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: list[list[list[float]]]

class GeoJsonLineString(BaseModel):
    type: str = "LineString"
    coordinates: list[list[float]]

class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

import uuid
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import String, ForeignKey, DateTime, Float, Boolean, Integer, JSON
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography

from app.models.base import Base
from app.models.enums import Visibility, TripStatus, StopStatus, StopType, MediaKind, MediaProcessingState, POIType

class Trip(Base):
    __tablename__ = "trip"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    status: Mapped[TripStatus] = mapped_column(default=TripStatus.PLANNED)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)
    
    cover_media_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("media_asset.id", ondelete="SET NULL", use_alter=True), nullable=True)
    
    cover_bounds: Mapped[Optional[Any]] = mapped_column(Geography(geometry_type='POLYGON', srid=4326), nullable=True)
    route_track: Mapped[Optional[Any]] = mapped_column(Geography(geometry_type='LINESTRING', srid=4326), nullable=True)
    total_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=True)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    stops: Mapped[List["Stop"]] = relationship("Stop", back_populates="trip", order_by="Stop.sort_order", cascade="all, delete-orphan")


class Stop(Base):
    __tablename__ = "stop"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    location: Mapped[Any] = mapped_column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    place_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    status: Mapped[StopStatus] = mapped_column(default=StopStatus.PLANNED)
    stop_type: Mapped[StopType] = mapped_column(default=StopType.OTHER)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)
    
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=True)
    
    cover_media_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("media_asset.id", ondelete="SET NULL", use_alter=True), nullable=True)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trip: Mapped["Trip"] = relationship("Trip", back_populates="stops")
    pois: Mapped[List["PointOfInterest"]] = relationship("PointOfInterest", back_populates="stop", cascade="all, delete-orphan")


class PointOfInterest(Base):
    __tablename__ = "point_of_interest"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stop.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    poi_type: Mapped[POIType] = mapped_column(default=POIType.OTHER)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    google_maps_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    location: Mapped[Any] = mapped_column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    stop: Mapped["Stop"] = relationship("Stop", back_populates="pois")


class MediaAsset(Base):
    __tablename__ = "media_asset"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[MediaKind] = mapped_column(nullable=False)
    processing_state: Mapped[MediaProcessingState] = mapped_column(default=MediaProcessingState.PENDING)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    original_path: Mapped[str] = mapped_column(String, nullable=False)
    original_sha256: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dominant_color: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    blurhash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gps_location: Mapped[Optional[Any]] = mapped_column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    
    caption: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    alt_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)
    
    derivative_paths: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    trip_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("trip.id", ondelete="SET NULL"), nullable=True)
    stop_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("stop.id", ondelete="SET NULL"), nullable=True)
    
    attached_to: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 'rv_profile' or 'traveler_profile'
    
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

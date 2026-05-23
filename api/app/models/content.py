import uuid
from datetime import datetime
from typing import Any, List, Optional

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.enums import (
    ActivityType,
    MediaKind,
    MediaProcessingState,
    POIType,
    PostType,
    PostStatus,
    StopStatus,
    StopType,
    TripStatus,
    Visibility,
)


class Trip(Base):
    __tablename__ = "trip"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[TripStatus] = mapped_column(
        SAEnum(TripStatus, values_callable=lambda x: [e.value for e in x], name="tripstatus", create_type=False),
        default=TripStatus.DRAFT,
    )
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)

    cover_media_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("media_asset.id", ondelete="SET NULL", use_alter=True), nullable=True)

    cover_bounds: Mapped[Optional[Any]] = mapped_column(Geography(geometry_type="POLYGON", srid=4326), nullable=True)
    route_track: Mapped[Optional[Any]] = mapped_column(Geography(geometry_type="LINESTRING", srid=4326), nullable=True)
    total_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_import_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("import_run.id", ondelete="SET NULL"), nullable=True)

    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cover_media: Mapped[Optional["MediaAsset"]] = relationship(
        "MediaAsset",
        foreign_keys=[cover_media_id],
        post_update=True,
    )
    stops: Mapped[List["Stop"]] = relationship("Stop", back_populates="trip", order_by="Stop.sort_order", cascade="all, delete-orphan")
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="trip")
    source_import_run: Mapped[Optional["ImportRun"]] = relationship(
        "ImportRun",
        foreign_keys=[source_import_run_id],
    )
    media: Mapped[List["MediaAsset"]] = relationship(
        "MediaAsset",
        foreign_keys="MediaAsset.trip_id",
        back_populates="trip",
    )


class SiteTextSection(Base):
    __tablename__ = "site_text_section"
    __table_args__ = (
        UniqueConstraint("page_key", "section_key", name="uq_site_text_section_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    page_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    heading: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cta_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cta_href: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Stop(Base):
    __tablename__ = "stop"
    __table_args__ = (
        UniqueConstraint("trip_id", "slug", name="uq_stop_trip_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    location: Mapped[Any] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    place_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    nights: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[StopStatus] = mapped_column(
        SAEnum(StopStatus, values_callable=lambda x: [e.value for e in x], name="stopstatus", create_type=False),
        default=StopStatus.DRAFT,
    )
    stop_type: Mapped[StopType] = mapped_column(default=StopType.OTHER)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)

    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    rv_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    rv_features: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    miles_from_previous: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_travel_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    would_stay_again: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    public_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    private_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    site_number_private: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reservation_private: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    timezone_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    cover_media_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("media_asset.id", ondelete="SET NULL", use_alter=True), nullable=True)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trip: Mapped["Trip"] = relationship("Trip", back_populates="stops")
    cover_media: Mapped[Optional["MediaAsset"]] = relationship(
        "MediaAsset",
        foreign_keys=[cover_media_id],
        post_update=True,
    )
    media: Mapped[List["MediaAsset"]] = relationship(
        "MediaAsset",
        foreign_keys="MediaAsset.stop_id",
        back_populates="stop",
    )
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="stop")
    pois: Mapped[List["PointOfInterest"]] = relationship("PointOfInterest", back_populates="stop", cascade="all, delete-orphan")


class ImportRun(Base):
    __tablename__ = "import_run"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String, nullable=False)
    trip_title_from_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="parsed")
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = "post"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("trip.id", ondelete="SET NULL"), nullable=True, index=True)
    stop_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("stop.id", ondelete="SET NULL"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)
    status: Mapped[PostStatus] = mapped_column(
        SAEnum(PostStatus, values_callable=lambda x: [e.value for e in x], name="poststatus", create_type=False),
        default=PostStatus.DRAFT,
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)

    post_type: Mapped[PostType] = mapped_column(
        SAEnum(PostType, values_callable=lambda x: [e.value for e in x], name="posttype", create_type=False),
        default=PostType.UPDATE,
    )
    activity_type: Mapped[Optional[ActivityType]] = mapped_column(
        SAEnum(ActivityType, values_callable=lambda x: [e.value for e in x], name="activitytype", create_type=False),
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    activity_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    activity_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    poi_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("point_of_interest.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trip: Mapped[Optional["Trip"]] = relationship("Trip", back_populates="posts")
    stop: Mapped[Optional["Stop"]] = relationship("Stop", back_populates="posts")
    media: Mapped[List["MediaAsset"]] = relationship("MediaAsset", back_populates="post")
    poi: Mapped[Optional["PointOfInterest"]] = relationship(
        "PointOfInterest",
        foreign_keys=[poi_id],
        post_update=True,
    )


class PointOfInterest(Base):
    __tablename__ = "point_of_interest"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stop.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    poi_type: Mapped[POIType] = mapped_column(default=POIType.OTHER)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    google_maps_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    location: Mapped[Any] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)

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
    gps_location: Mapped[Optional[Any]] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)

    caption: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    alt_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)

    derivative_paths: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    trip_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("trip.id", ondelete="SET NULL"), nullable=True)
    stop_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("stop.id", ondelete="SET NULL"), nullable=True)
    post_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("post.id", ondelete="SET NULL"), nullable=True)

    attached_to: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 'rv_profile' or 'traveler_profile'

    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trip: Mapped[Optional["Trip"]] = relationship(
        "Trip",
        foreign_keys=[trip_id],
        back_populates="media",
    )
    stop: Mapped[Optional["Stop"]] = relationship(
        "Stop",
        foreign_keys=[stop_id],
        back_populates="media",
    )
    post: Mapped[Optional["Post"]] = relationship("Post", back_populates="media")

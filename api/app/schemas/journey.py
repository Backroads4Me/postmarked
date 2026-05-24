import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from app.models.enums import ActivityType, PostType, StopStatus, TripStatus, Visibility
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut


class PublicPOISummary(BaseModel):
    """Allowlisted public POI fields — intentionally excludes notes."""
    id: uuid.UUID
    label: str
    poi_type: str
    google_maps_url: Optional[str] = None
    latitude: float
    longitude: float


class MediaGPSPoint(BaseModel):
    """Slim GPS coordinate for a photo, used for map dots on stop detail."""
    media_id: uuid.UUID
    latitude: float
    longitude: float


class PublicStopSummary(BaseResponse):
    id: uuid.UUID
    trip_id: uuid.UUID
    trip_slug: Optional[str] = None
    trip_title: Optional[str] = None
    slug: str
    title: str
    summary: Optional[str] = None
    place_name: Optional[str] = None
    address_label: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    nights: Optional[int] = None
    status: StopStatus
    sort_order: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rv_features: List[str] = []
    miles_from_previous: Optional[float] = None
    estimated_travel_time: Optional[str] = None
    public_note: Optional[str] = None
    cover_media: Optional[MediaAssetOut] = None
    is_current: bool = False


class PublicPostSummary(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    body: Optional[str] = None
    posted_at: datetime
    is_featured: bool
    stop: Optional[PublicStopSummary] = None
    media: List[MediaAssetOut] = []

    post_type: PostType = PostType.UPDATE
    activity_type: Optional[ActivityType] = None
    summary: Optional[str] = None
    activity_started_at: Optional[datetime] = None
    activity_ended_at: Optional[datetime] = None
    poi: Optional[PublicPOISummary] = None


class PublicTripSegmentSummary(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    summary: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: TripStatus
    total_distance_meters: Optional[float] = None
    stops_completed: int = 0
    stops_total: int = 0
    cover_media: Optional[MediaAssetOut] = None


class PublicTripSegmentDetail(PublicTripSegmentSummary):
    body: Optional[str] = None
    stops: List[PublicStopSummary] = []
    posts: List[PublicPostSummary] = []


class PublicStopSibling(BaseModel):
    """Slim previous/next nav handle for the stop detail page."""
    slug: str
    title: str


class PublicPostSibling(BaseModel):
    """Slim previous/next activity nav handle."""
    slug: str
    title: str
    stop_slug: str
    trip_slug: str


class PublicStopDetail(PublicStopSummary):
    """Full public-facing stop view: body + own media + on-stop posts + nav."""
    body: Optional[str] = None
    trip_slug: str
    trip_title: str
    timezone_id: Optional[str] = None
    media: List[MediaAssetOut] = []
    posts: List["PublicPostSummary"] = []
    pois: List[PublicPOISummary] = []
    media_with_gps: List[MediaGPSPoint] = []
    prev: Optional[PublicStopSibling] = None
    next: Optional[PublicStopSibling] = None


class HomeOut(BaseModel):
    current_stop: Optional[PublicStopSummary] = None
    next_stop: Optional[PublicStopSummary] = None
    previous_stop: Optional[PublicStopSummary] = None
    recent_stops: List[PublicStopSummary] = []
    recent_posts: List[PublicPostSummary] = []
    active_trip_segment: Optional[PublicTripSegmentSummary] = None
    upcoming_stops: List[PublicStopSummary] = []


class RecentUpdate(BaseModel):
    """
    Unified entry in the chronological timeline feed. `kind` discriminates
    between a post and a stop; per-kind fields are optional.

    Sorted by `posted_at` (which is `start_date` for stops).
    """
    kind: Literal["post", "stop"]
    id: uuid.UUID
    title: str
    slug: Optional[str] = None
    summary: Optional[str] = None
    body: Optional[str] = None  # post body
    posted_at: datetime
    trip_id: Optional[uuid.UUID] = None
    trip_title: Optional[str] = None
    trip_slug: Optional[str] = None
    stop_id: Optional[uuid.UUID] = None
    stop_title: Optional[str] = None
    stop_slug: Optional[str] = None
    place_name: Optional[str] = None
    address_label: Optional[str] = None
    cover_media: Optional[MediaAssetOut] = None
    media: List[MediaAssetOut] = []


class PublicPostDetail(PublicPostSummary):
    """Full public-facing post view for the activity detail page."""
    stop_slug: str
    stop_title: str
    stop_place_name: Optional[str] = None
    stop_address_label: Optional[str] = None
    trip_slug: str
    trip_title: str
    stop_timezone_id: Optional[str] = None
    prev_activity: Optional[PublicPostSibling] = None
    next_activity: Optional[PublicPostSibling] = None


PublicStopDetail.model_rebuild()


class TimelineOut(BaseModel):
    updates: List[RecentUpdate] = []
    limit: int
    offset: int
    has_more: bool = False

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import ActivityType, PostType, StopStatus, TripStatus
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut


class PublicPOISummary(BaseModel):
    """Allowlisted public POI fields — intentionally excludes notes."""
    id: uuid.UUID
    label: str
    poi_type: str
    google_maps_url: str | None = None
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
    trip_slug: str | None = None
    trip_title: str | None = None
    slug: str
    title: str
    summary: str | None = None
    place_name: str | None = None
    address_label: str | None = None
    start_date: datetime
    end_date: datetime | None = None
    nights: int | None = None
    status: StopStatus
    sort_order: int
    latitude: float | None = None
    longitude: float | None = None
    rv_features: list[str] = []
    miles_from_previous: float | None = None
    estimated_travel_time: str | None = None
    public_note: str | None = None
    cover_media: MediaAssetOut | None = None
    is_current: bool = False


class PublicPostSummary(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    body: str | None = None
    posted_at: datetime
    is_featured: bool
    stop: PublicStopSummary | None = None
    media: list[MediaAssetOut] = []

    post_type: PostType = PostType.UPDATE
    activity_type: ActivityType | None = None
    summary: str | None = None
    activity_started_at: datetime | None = None
    activity_ended_at: datetime | None = None
    poi: PublicPOISummary | None = None


class PublicTripSegmentSummary(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    summary: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: TripStatus
    total_distance_meters: float | None = None
    stops_completed: int = 0
    stops_total: int = 0
    cover_media: MediaAssetOut | None = None


class PublicTripSegmentDetail(PublicTripSegmentSummary):
    body: str | None = None
    stops: list[PublicStopSummary] = []
    posts: list[PublicPostSummary] = []


class PublicStopSibling(BaseModel):
    """Slim previous/next nav handle for the stop detail page."""
    slug: str
    title: str
    address_label: str | None = None


class PublicPostSibling(BaseModel):
    """Slim previous/next activity nav handle."""
    slug: str
    title: str
    stop_slug: str
    trip_slug: str


class PublicStopDetail(PublicStopSummary):
    """Full public-facing stop view: body + own media + on-stop posts + nav."""
    body: str | None = None
    trip_slug: str
    trip_title: str
    timezone_id: str | None = None
    media: list[MediaAssetOut] = []
    posts: list["PublicPostSummary"] = []
    pois: list[PublicPOISummary] = []
    media_with_gps: list[MediaGPSPoint] = []
    is_live_current: bool = False
    prev: PublicStopSibling | None = None
    next: PublicStopSibling | None = None


class WeatherCurrent(BaseModel):
    temp: int
    label: str


class WeatherDay(BaseModel):
    day: str
    high: int
    low: int
    label: str


class WeatherOut(BaseModel):
    current: WeatherCurrent
    forecast: list[WeatherDay] = []
    unit: Literal["fahrenheit", "celsius"] = "fahrenheit"


class HomeOut(BaseModel):
    current_stop: PublicStopSummary | None = None
    current_stop_is_live: bool = False
    current_stop_kind: Literal["live", "previous", "upcoming"] | None = None
    next_stop: PublicStopSummary | None = None
    previous_stop: PublicStopSummary | None = None
    recent_stops: list[PublicStopSummary] = []
    recent_posts: list[PublicPostSummary] = []
    active_trip_segment: PublicTripSegmentSummary | None = None
    upcoming_stops: list[PublicStopSummary] = []
    has_more: bool = False
    weather: WeatherOut | None = None


class RecentUpdate(BaseModel):
    """
    Unified entry in the chronological timeline feed. `kind` discriminates
    between a post and a stop; per-kind fields are optional.

    Sorted by `posted_at` (which is `start_date` for stops).
    """
    kind: Literal["post", "stop"]
    id: uuid.UUID
    title: str
    slug: str | None = None
    summary: str | None = None
    body: str | None = None  # post body
    posted_at: datetime
    trip_id: uuid.UUID | None = None
    trip_title: str | None = None
    trip_slug: str | None = None
    stop_id: uuid.UUID | None = None
    stop_title: str | None = None
    stop_slug: str | None = None
    place_name: str | None = None
    address_label: str | None = None
    cover_media: MediaAssetOut | None = None
    media: list[MediaAssetOut] = []


class PublicPostDetail(PublicPostSummary):
    """Full public-facing post view for the activity detail page."""
    stop_slug: str
    stop_title: str
    stop_place_name: str | None = None
    stop_address_label: str | None = None
    trip_slug: str
    trip_title: str
    stop_timezone_id: str | None = None
    prev_activity: PublicPostSibling | None = None
    next_activity: PublicPostSibling | None = None
    prev_post: PublicPostSibling | None = None
    next_post: PublicPostSibling | None = None


PublicStopDetail.model_rebuild()


class TimelineOut(BaseModel):
    updates: list[RecentUpdate] = []
    limit: int
    offset: int
    has_more: bool = False

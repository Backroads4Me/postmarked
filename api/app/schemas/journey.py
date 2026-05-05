import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from app.models.enums import JourneyStatus, StopStatus, StopType, TripStatus, Visibility
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut


class PublicStopSummary(BaseResponse):
    id: uuid.UUID
    trip_id: uuid.UUID
    slug: str
    title: str
    summary: Optional[str] = None
    place_name: Optional[str] = None
    address_label: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    nights: Optional[int] = None
    status: StopStatus
    stop_type: StopType
    sort_order: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rv_features: List[str] = []
    miles_from_previous: Optional[float] = None
    estimated_travel_time: Optional[str] = None
    public_note: Optional[str] = None
    cover_media: Optional[MediaAssetOut] = None


class PublicPostSummary(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    body: Optional[str] = None
    posted_at: datetime
    is_featured: bool
    stop: Optional[PublicStopSummary] = None
    media: List[MediaAssetOut] = []


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


class PublicTripSegmentDetail(PublicTripSegmentSummary):
    body: Optional[str] = None
    stops: List[PublicStopSummary] = []
    posts: List[PublicPostSummary] = []


class PublicStopSibling(BaseModel):
    """Slim previous/next nav handle for the stop detail page."""
    slug: str
    title: str


class PublicStopDetail(PublicStopSummary):
    """Full public-facing stop view: body + own media + on-stop posts + nav."""
    body: Optional[str] = None
    trip_slug: str
    trip_title: str
    media: List[MediaAssetOut] = []
    posts: List["PublicPostSummary"] = []
    prev: Optional[PublicStopSibling] = None
    next: Optional[PublicStopSibling] = None


class PublicJourneySummary(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    summary: Optional[str] = None
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    status: JourneyStatus
    current_location_note: Optional[str] = None


class PublicPlannedStopSummary(BaseResponse):
    """
    Public-safe view of an imported PlannedStop. Strips cost/fuel/reservation/
    contact fields by simply not declaring them — the schema is an allowlist,
    not a denylist (avoid future leakage by addition).
    """
    id: uuid.UUID
    trip_id: uuid.UUID
    name: str
    arrival_date: Optional[date] = None
    departure_date: Optional[date] = None
    nights: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    miles_from_previous: Optional[float] = None
    estimated_travel_time: Optional[str] = None


class HomeOut(BaseModel):
    journey: Optional[PublicJourneySummary] = None
    current_stop: Optional[PublicStopSummary] = None
    next_stop: Optional[PublicStopSummary] = None
    recent_stops: List[PublicStopSummary] = []
    recent_posts: List[PublicPostSummary] = []
    active_trip_segment: Optional[PublicTripSegmentSummary] = None
    upcoming_planned_stops: List[PublicPlannedStopSummary] = []


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
    stop_type: Optional[StopType] = None
    cover_media: Optional[MediaAssetOut] = None
    media: List[MediaAssetOut] = []


PublicStopDetail.model_rebuild()


class TimelineOut(BaseModel):
    """Paginated cross-trip activity feed for the journey."""
    journey: Optional[PublicJourneySummary] = None
    updates: List[RecentUpdate] = []
    limit: int
    offset: int
    has_more: bool = False


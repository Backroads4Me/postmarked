import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.auth_config import fastapi_users_app
from app.db import get_async_session
from app.models.content import Journey, MediaAsset, PlannedStop, Post, Stop, Trip
from app.models.enums import JourneyStatus, PlannedStopImportState, StopStatus, TripStatus, Visibility
from app.schemas.journey import (
    HomeOut,
    PublicJourneySummary,
    PublicPlannedStopSummary,
    PublicPostSummary,
    PublicStopSummary,
    PublicTripSegmentDetail,
    PublicTripSegmentSummary,
    RecentUpdate,
    TimelineOut,
)

router = APIRouter(tags=["journey"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)


def _is_admin(user) -> bool:
    return bool(user and getattr(getattr(user, "role", None), "value", None) == "admin")


def _public_only(query, model, user):
    if _is_admin(user):
        return query
    return query.where(model.visibility == Visibility.PUBLIC)


async def _active_journey(session: AsyncSession, user) -> Optional[Journey]:
    """
    Return the single ACTIVE journey, falling back to most-recent non-archived
    if none are explicitly active. Anonymous viewers only see public journeys.
    """
    query = (
        select(Journey)
        .options(selectinload(Journey.current_stop))
        .where(Journey.status == JourneyStatus.ACTIVE)
        .order_by(Journey.created_at.desc())
    )
    if not _is_admin(user):
        query = query.where(Journey.visibility == Visibility.PUBLIC)
    result = await session.execute(query)
    journey = result.scalars().first()
    if journey:
        return journey

    # Fallback: any non-archived journey, newest first.
    fallback = (
        select(Journey)
        .options(selectinload(Journey.current_stop))
        .where(Journey.status != JourneyStatus.ARCHIVED)
        .order_by(Journey.created_at.desc())
    )
    if not _is_admin(user):
        fallback = fallback.where(Journey.visibility == Visibility.PUBLIC)
    return (await session.execute(fallback)).scalars().first()


async def _coordinates_for_stops(session: AsyncSession, stops: Iterable[Stop]) -> dict[uuid.UUID, tuple[float, float]]:
    stop_ids = [stop.id for stop in stops]
    if not stop_ids:
        return {}

    point = cast(Stop.location, Geometry(geometry_type="POINT", srid=4326))
    result = await session.execute(
        select(
            Stop.id,
            func.ST_Y(point).label("latitude"),
            func.ST_X(point).label("longitude"),
        ).where(Stop.id.in_(stop_ids))
    )
    return {row.id: (row.latitude, row.longitude) for row in result.all()}


def _visible_media(media: list[MediaAsset], user) -> list[MediaAsset]:
    if _is_admin(user):
        return media
    return [asset for asset in media if asset.visibility == Visibility.PUBLIC]


def _stop_out(stop: Optional[Stop], coords: dict[uuid.UUID, tuple[float, float]], user) -> Optional[PublicStopSummary]:
    if not stop:
        return None
    if not _is_admin(user) and stop.visibility != Visibility.PUBLIC:
        return None

    latitude, longitude = coords.get(stop.id, (None, None))
    return PublicStopSummary(
        id=stop.id,
        trip_id=stop.trip_id,
        trip_slug=stop.trip.slug if stop.trip else None,
        trip_title=stop.trip.title if stop.trip else None,
        slug=stop.slug,
        title=stop.title,
        summary=stop.summary,
        place_name=stop.place_name,
        address_label=stop.address_label,
        start_date=stop.start_date,
        end_date=stop.end_date,
        nights=stop.nights,
        status=stop.status,
        stop_type=stop.stop_type,
        sort_order=stop.sort_order,
        latitude=latitude,
        longitude=longitude,
        rv_features=stop.rv_features or [],
        miles_from_previous=stop.miles_from_previous,
        estimated_travel_time=stop.estimated_travel_time,
        public_note=stop.public_note,
        cover_media=stop.cover_media if stop.cover_media and (_is_admin(user) or stop.cover_media.visibility == Visibility.PUBLIC) else None,
    )


def _journey_out(journey: Optional[Journey]) -> Optional[PublicJourneySummary]:
    if not journey:
        return None
    return PublicJourneySummary(
        id=journey.id,
        slug=journey.slug,
        title=journey.title,
        summary=journey.summary,
        starts_on=journey.starts_on,
        ends_on=journey.ends_on,
        status=journey.status,
        current_location_note=journey.current_location_note,
    )


def _trip_summary_out(trip: Optional[Trip], stops: list[Stop]) -> Optional[PublicTripSegmentSummary]:
    if not trip:
        return None
    completed_statuses = {StopStatus.ACTIVE, StopStatus.PUBLISHED, StopStatus.ARCHIVED}
    return PublicTripSegmentSummary(
        id=trip.id,
        slug=trip.slug,
        title=trip.title,
        summary=trip.summary,
        start_date=trip.start_date,
        end_date=trip.end_date,
        status=trip.status,
        total_distance_meters=trip.total_distance_meters,
        stops_completed=sum(1 for stop in stops if stop.status in completed_statuses),
        stops_total=len(stops),
    )


async def _post_out(post: Post, coords: dict[uuid.UUID, tuple[float, float]], user) -> PublicPostSummary:
    stop = _stop_out(post.stop, coords, user)
    return PublicPostSummary(
        id=post.id,
        slug=post.slug,
        title=post.title,
        body=post.body,
        posted_at=post.posted_at,
        is_featured=post.is_featured,
        stop=stop,
        media=_visible_media(post.media, user),
    )


def _post_to_update(post: Post, user) -> RecentUpdate:
    visible = _visible_media(post.media, user)
    return RecentUpdate(
        kind="post",
        id=post.id,
        title=post.title,
        slug=post.slug,
        summary=(post.body[:200] if post.body else None),
        body=post.body,
        posted_at=post.posted_at,
        trip_id=post.trip_id,
        trip_title=post.trip.title if post.trip else None,
        trip_slug=post.trip.slug if post.trip else None,
        stop_id=post.stop_id,
        stop_title=post.stop.title if post.stop else None,
        stop_slug=post.stop.slug if post.stop else None,
        place_name=post.stop.place_name if post.stop else None,
        media=visible,
    )


def _stop_to_update(stop: Stop, user) -> RecentUpdate:
    show_cover = stop.cover_media and (
        _is_admin(user) or stop.cover_media.visibility == Visibility.PUBLIC
    )
    return RecentUpdate(
        kind="stop",
        id=stop.id,
        title=stop.title,
        slug=stop.slug,
        summary=stop.summary,
        posted_at=stop.start_date,
        trip_id=stop.trip_id,
        trip_title=stop.trip.title if stop.trip else None,
        trip_slug=stop.trip.slug if stop.trip else None,
        stop_id=stop.id,
        stop_title=stop.title,
        stop_slug=stop.slug,
        place_name=stop.place_name,
        stop_type=stop.stop_type,
        cover_media=stop.cover_media if show_cover else None,
    )


@router.get("/home", response_model=HomeOut)
async def get_home(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    journey = await _active_journey(session, user)
    if not journey:
        return HomeOut()

    stops_query = (
        select(Stop)
        .where(Stop.journey_id == journey.id)
        .options(selectinload(Stop.cover_media), selectinload(Stop.trip))
        .order_by(Stop.start_date.asc())
    )
    stops_query = _public_only(stops_query, Stop, user)
    stops = list((await session.execute(stops_query)).scalars().all())
    coords = await _coordinates_for_stops(session, stops)

    current_stop = _stop_out(journey.current_stop, coords, user)
    if not current_stop:
        active_stop = next((stop for stop in stops if stop.status == StopStatus.ACTIVE), None)
        current_stop = _stop_out(active_stop, coords, user)
    if not current_stop and stops:
        now = datetime.now(timezone.utc)
        latest_stop = next((stop for stop in reversed(stops) if stop.start_date <= now), stops[-1])
        current_stop = _stop_out(latest_stop, coords, user)

    current_sort_order = current_stop.sort_order if current_stop else -1
    next_stop_model = next((stop for stop in stops if stop.sort_order > current_sort_order), None)

    posts_query = (
        select(Post)
        .where(Post.journey_id == journey.id)
        .options(
            selectinload(Post.stop).selectinload(Stop.cover_media),
            selectinload(Post.media),
        )
        .order_by(Post.posted_at.desc())
        .limit(8)
    )
    posts_query = _public_only(posts_query, Post, user)
    posts = list((await session.execute(posts_query)).scalars().all())
    post_stop_coords = await _coordinates_for_stops(session, [post.stop for post in posts if post.stop])
    coords.update(post_stop_coords)

    active_trip = None
    active_trip_stops: list[Stop] = []
    if current_stop:
        active_trip = await session.get(Trip, current_stop.trip_id)
        active_trip_stops = [stop for stop in stops if stop.trip_id == current_stop.trip_id]
    if not active_trip:
        trip_query = select(Trip).where(Trip.journey_id == journey.id, Trip.status == TripStatus.ACTIVE)
        trip_query = _public_only(trip_query, Trip, user)
        active_trip = (await session.execute(trip_query)).scalars().first()
        active_trip_stops = [stop for stop in stops if active_trip and stop.trip_id == active_trip.id]

    # Upcoming planned-but-not-realized stops (RV Trip Wizard imports).
    # Skip stops the importer marked removed and stops already promoted to a real Stop.
    today = datetime.now(timezone.utc).date()
    planned_query = (
        select(PlannedStop)
        .where(
            PlannedStop.journey_id == journey.id,
            PlannedStop.import_state.notin_(
                [
                    PlannedStopImportState.REMOVED_FROM_LATEST_IMPORT,
                    PlannedStopImportState.CONVERTED_TO_STOP,
                ]
            ),
            PlannedStop.matched_stop_id.is_(None),
        )
        .order_by(
            PlannedStop.arrival_date.asc().nulls_last(),
            PlannedStop.source_sequence.asc(),
        )
        .limit(5)
    )
    # Anonymous viewers only see planned stops on a public trip.
    if not _is_admin(user):
        planned_query = planned_query.join(Trip, PlannedStop.trip_id == Trip.id).where(
            Trip.visibility == Visibility.PUBLIC
        )
    planned_rows = (await session.execute(planned_query)).scalars().all()
    upcoming_planned = [
        PublicPlannedStopSummary(
            id=ps.id,
            trip_id=ps.trip_id,
            name=ps.name,
            arrival_date=ps.arrival_date,
            departure_date=ps.departure_date,
            nights=ps.nights,
            latitude=ps.latitude,
            longitude=ps.longitude,
            address=ps.address,
            miles_from_previous=ps.miles_from_previous,
            estimated_travel_time=ps.estimated_travel_time,
        )
        for ps in planned_rows
        # Drop ones whose arrival date is in the past — those are stale plans.
        if ps.arrival_date is None or ps.arrival_date >= today
    ]

    return HomeOut(
        journey=_journey_out(journey),
        current_stop=current_stop,
        next_stop=_stop_out(next_stop_model, coords, user),
        recent_stops=[_stop_out(stop, coords, user) for stop in reversed(stops[-5:]) if _stop_out(stop, coords, user)],
        recent_posts=[await _post_out(post, coords, user) for post in posts],
        active_trip_segment=_trip_summary_out(active_trip, active_trip_stops),
        upcoming_planned_stops=upcoming_planned,
    )


@router.get("/timeline", response_model=TimelineOut)
async def get_timeline(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    trip_slug: Optional[str] = None,
):
    """
    Cross-trip activity feed for the active journey, newest first.

    Mixes posts and stops into one chronological list (`updates[]`). Pagination
    via offset/limit; we over-fetch each side then merge in Python. Acceptable
    for V1 data sizes; revisit with a SQL UNION if the journey gets long.
    """
    journey = await _active_journey(session, user)
    if not journey:
        return TimelineOut(updates=[], limit=limit, offset=offset, has_more=False)

    fetch_window = limit + offset + 1  # +1 to detect has_more cheaply

    # Stops — only published/active count for the public timeline.
    stops_query = (
        select(Stop)
        .where(Stop.journey_id == journey.id)
        .options(
            selectinload(Stop.trip),
            selectinload(Stop.cover_media),
        )
        .order_by(Stop.start_date.desc())
        .limit(fetch_window)
    )
    if trip_slug:
        stops_query = stops_query.join(Trip, Stop.trip_id == Trip.id).where(Trip.slug == trip_slug)
    if not _is_admin(user):
        stops_query = stops_query.where(
            Stop.visibility == Visibility.PUBLIC,
            Stop.status.in_([StopStatus.PUBLISHED, StopStatus.ACTIVE]),
        )
    stops = (await session.execute(stops_query)).scalars().all()

    # Posts.
    posts_query = (
        select(Post)
        .where(Post.journey_id == journey.id)
        .options(
            selectinload(Post.stop),
            selectinload(Post.trip),
            selectinload(Post.media),
        )
        .order_by(Post.posted_at.desc())
        .limit(fetch_window)
    )
    if trip_slug:
        posts_query = posts_query.join(Trip, Post.trip_id == Trip.id).where(Trip.slug == trip_slug)
    if not _is_admin(user):
        posts_query = posts_query.where(Post.visibility == Visibility.PUBLIC)
    posts = (await session.execute(posts_query)).scalars().all()

    merged: list[RecentUpdate] = [_stop_to_update(s, user) for s in stops] + [
        _post_to_update(p, user) for p in posts
    ]
    merged.sort(key=lambda u: u.posted_at, reverse=True)

    page = merged[offset : offset + limit]
    has_more = len(merged) > offset + limit

    return TimelineOut(
        journey=_journey_out(journey),
        updates=page,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get("/trip-segments", response_model=list[PublicTripSegmentSummary])
async def list_trip_segments(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    journey = await _active_journey(session, user)
    if not journey:
        return []

    trip_query = select(Trip).where(Trip.journey_id == journey.id).order_by(Trip.start_date.asc())
    trip_query = _public_only(trip_query, Trip, user)
    trips = list((await session.execute(trip_query)).scalars().all())

    stop_query = select(Stop).where(Stop.journey_id == journey.id)
    stop_query = _public_only(stop_query, Stop, user)
    stops = list((await session.execute(stop_query)).scalars().all())

    return [_trip_summary_out(trip, [stop for stop in stops if stop.trip_id == trip.id]) for trip in trips]


@router.get("/trip-segments/{slug}", response_model=PublicTripSegmentDetail)
async def get_trip_segment(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    trip_query = select(Trip).where(Trip.slug == slug).options(selectinload(Trip.stops).selectinload(Stop.cover_media))
    trip_query = _public_only(trip_query, Trip, user)
    trip = (await session.execute(trip_query)).scalars().first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip segment not found")

    stops = sorted(
        list(trip.stops),
        key=lambda stop: (
            stop.start_date,
            stop.sort_order if stop.sort_order is not None else 999999,
            stop.title,
        ),
    )
    if not _is_admin(user):
        stops = [stop for stop in stops if stop.visibility == Visibility.PUBLIC]
    coords = await _coordinates_for_stops(session, stops)

    posts_query = (
        select(Post)
        .where(Post.trip_id == trip.id)
        .options(
            selectinload(Post.stop).selectinload(Stop.cover_media),
            selectinload(Post.media),
        )
        .order_by(Post.posted_at.desc())
    )
    posts_query = _public_only(posts_query, Post, user)
    posts = list((await session.execute(posts_query)).scalars().all())

    summary = _trip_summary_out(trip, stops)
    return PublicTripSegmentDetail(
        **summary.model_dump(),
        body=trip.body,
        stops=[_stop_out(stop, coords, user) for stop in stops if _stop_out(stop, coords, user)],
        posts=[await _post_out(post, coords, user) for post in posts],
    )

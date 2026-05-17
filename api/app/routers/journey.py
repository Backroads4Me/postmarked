import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.auth_config import fastapi_users_app
from app.db import get_async_session
from app.models.content import MediaAsset, PlannedStop, Post, Stop, Trip
from app.models.enums import PlannedStopImportState, StopStatus, TripStatus, Visibility
from app.schemas.journey import (
    HomeOut,
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


async def _coordinates_for_stops(session: AsyncSession, stops) -> dict[uuid.UUID, tuple[float, float]]:
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
    stops_query = (
        select(Stop)
        .options(selectinload(Stop.cover_media), selectinload(Stop.trip))
        .order_by(Stop.start_date.asc())
    )
    stops_query = _public_only(stops_query, Stop, user)
    stops = list((await session.execute(stops_query)).scalars().all())
    coords = await _coordinates_for_stops(session, stops)

    # Current stop: explicit is_current flag, then active status, then most recent past date.
    current_stop_model = next((s for s in stops if s.is_current), None)
    if not current_stop_model:
        current_stop_model = next((s for s in stops if s.status == StopStatus.ACTIVE), None)
    if not current_stop_model and stops:
        now = datetime.now(timezone.utc)
        current_stop_model = next(
            (s for s in reversed(stops) if s.start_date <= now), stops[-1]
        )

    current_stop = _stop_out(current_stop_model, coords, user)
    current_sort_order = current_stop.sort_order if current_stop else -1
    next_stop_model = next((s for s in stops if s.sort_order > current_sort_order), None)

    posts_query = (
        select(Post)
        .options(
            selectinload(Post.stop).selectinload(Stop.cover_media),
            selectinload(Post.media),
        )
        .order_by(Post.posted_at.desc())
        .limit(8)
    )
    posts_query = _public_only(posts_query, Post, user)
    posts = list((await session.execute(posts_query)).scalars().all())
    post_stop_coords = await _coordinates_for_stops(session, [p.stop for p in posts if p.stop])
    coords.update(post_stop_coords)

    active_trip = None
    active_trip_stops: list[Stop] = []
    if current_stop:
        active_trip = await session.get(Trip, current_stop.trip_id)
        active_trip_stops = [s for s in stops if s.trip_id == current_stop.trip_id]
    if not active_trip:
        trip_query = select(Trip).where(Trip.status == TripStatus.ACTIVE)
        trip_query = _public_only(trip_query, Trip, user)
        active_trip = (await session.execute(trip_query)).scalars().first()
        active_trip_stops = [s for s in stops if active_trip and s.trip_id == active_trip.id]

    today = datetime.now(timezone.utc).date()
    planned_query = (
        select(PlannedStop)
        .where(
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
        if ps.arrival_date is None or ps.arrival_date >= today
    ]

    return HomeOut(
        current_stop=current_stop,
        next_stop=_stop_out(next_stop_model, coords, user),
        recent_stops=[_stop_out(s, coords, user) for s in reversed(stops[-5:]) if _stop_out(s, coords, user)],
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
    fetch_window = limit + offset + 1

    stops_query = (
        select(Stop)
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

    posts_query = (
        select(Post)
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
    trip_query = select(Trip).order_by(Trip.start_date.asc())
    trip_query = _public_only(trip_query, Trip, user)
    trips = list((await session.execute(trip_query)).scalars().all())

    stop_query = select(Stop)
    stop_query = _public_only(stop_query, Stop, user)
    stops = list((await session.execute(stop_query)).scalars().all())

    return [_trip_summary_out(trip, [s for s in stops if s.trip_id == trip.id]) for trip in trips]


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
        stops = [s for s in stops if s.visibility == Visibility.PUBLIC]
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
        stops=[_stop_out(s, coords, user) for s in stops if _stop_out(s, coords, user)],
        posts=[await _post_out(post, coords, user) for post in posts],
    )

import uuid

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.auth_config import fastapi_users_app
from app.db import get_async_session
from app.models.content import MediaAsset, PointOfInterest, Post, Stop, Trip
from app.models.enums import PostStatus, PostType, StopStatus, TripStatus, Visibility
from app.schemas.journey import (
    MediaGPSPoint,
    PublicPOISummary,
    PublicPostDetail,
    PublicPostSibling,
    PublicPostSummary,
    PublicStopDetail,
    PublicStopSibling,
)
from app.services.visibility import visible_ready_cover_media, visible_ready_media

router = APIRouter(prefix="/trips", tags=["stops"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)


async def _batch_poi_coords(
    session: AsyncSession, poi_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[float, float]]:
    if not poi_ids:
        return {}
    point = cast(PointOfInterest.location, Geometry(geometry_type="POINT", srid=4326))
    rows = (await session.execute(
        select(PointOfInterest.id, func.ST_Y(point).label("lat"), func.ST_X(point).label("lon"))
        .where(PointOfInterest.id.in_(poi_ids))
    )).all()
    return {row.id: (row.lat, row.lon) for row in rows}


def _is_admin(user) -> bool:
    return bool(user and getattr(getattr(user, "role", None), "value", None) == "admin")


def _reader_visible(query, model, user):
    if not user:
        return query.where(model.visibility == Visibility.PUBLIC)
    return query


@router.get("/{trip_slug}/stops/{stop_slug}", response_model=PublicStopDetail)
async def get_stop(
    trip_slug: str,
    stop_slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    """
    Public stop-detail view. Returns 404 (not 403) when the trip or stop is
    not visible to the caller. Includes own media, posts attached to the stop,
    and prev/next siblings within the trip.
    """
    query = (
        select(Stop)
        .join(Trip, Stop.trip_id == Trip.id)
        .where(Trip.slug == trip_slug, Stop.slug == stop_slug)
        .options(
            selectinload(Stop.cover_media),
            selectinload(Stop.trip),
            selectinload(Stop.media),
            selectinload(Stop.pois),
        )
    )

    query = query.where(
        Trip.status == TripStatus.PUBLISHED,
        Stop.status == StopStatus.PUBLISHED,
    )
    if not user:
        query = query.where(Trip.visibility == Visibility.PUBLIC, Stop.visibility == Visibility.PUBLIC)

    stop = (await session.execute(query)).scalars().first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    # Lat/lon
    point = cast(Stop.location, Geometry(geometry_type="POINT", srid=4326))
    coord_row = await session.execute(
        select(func.ST_Y(point), func.ST_X(point)).where(Stop.id == stop.id)
    )
    coord = coord_row.first()
    latitude, longitude = (coord[0], coord[1]) if coord else (None, None)

    # Own media (assets directly attached to this stop). Post media also carries
    # stop_id for scoping, but it should render only through its published post.
    own_media = visible_ready_media([m for m in (stop.media or []) if m.post_id is None], user)

    # Posts pinned to this stop — fetched here so we can batch all POI coord lookups below
    posts_query = (
        select(Post)
        .where(Post.stop_id == stop.id)
        .options(selectinload(Post.media), selectinload(Post.stop), selectinload(Post.poi))
        .order_by(Post.posted_at.desc())
    )
    posts_query = _reader_visible(posts_query, Post, user).where(Post.status == PostStatus.PUBLISHED)
    posts_rows = (await session.execute(posts_query)).scalars().all()

    # Single batch query for all POI coordinates needed on this page
    stop_poi_ids = [poi.id for poi in (stop.pois or [])]
    post_poi_ids = [p.poi.id for p in posts_rows if p.poi]
    poi_coords_map = await _batch_poi_coords(session, list(set(stop_poi_ids + post_poi_ids)))

    pois_out: list[PublicPOISummary] = []
    for poi in (stop.pois or []):
        coords = poi_coords_map.get(poi.id, (0.0, 0.0))
        pois_out.append(PublicPOISummary(
            id=poi.id,
            label=poi.label,
            poi_type=poi.poi_type.value,
            google_maps_url=poi.google_maps_url,
            latitude=coords[0],
            longitude=coords[1],
        ))

    # Media GPS dots — only photos with gps_location set
    media_gps_out: list[MediaGPSPoint] = []
    if own_media:
        gps_ids = [m.id for m in own_media if m.gps_location is not None]
        if gps_ids:
            gps_point = cast(MediaAsset.gps_location, Geometry(geometry_type="POINT", srid=4326))
            gps_rows = (await session.execute(
                select(
                    MediaAsset.id,
                    func.ST_Y(gps_point).label("lat"),
                    func.ST_X(gps_point).label("lon"),
                ).where(MediaAsset.id.in_(gps_ids))
            )).all()
            media_gps_out = [
                MediaGPSPoint(media_id=row.id, latitude=row.lat, longitude=row.lon)
                for row in gps_rows
            ]

    posts_out: list[PublicPostSummary] = []
    for p in posts_rows:
        visible_media = visible_ready_media(p.media or [], user)
        poi_out = None
        if p.poi:
            coords = poi_coords_map.get(p.poi.id, (0.0, 0.0))
            poi_out = PublicPOISummary(
                id=p.poi.id,
                label=p.poi.label,
                poi_type=p.poi.poi_type.value,
                google_maps_url=p.poi.google_maps_url,
                latitude=coords[0],
                longitude=coords[1],
            )
        posts_out.append(
            PublicPostSummary(
                id=p.id,
                slug=p.slug,
                title=p.title,
                body=p.body,
                posted_at=p.posted_at,
                is_featured=p.is_featured,
                stop=None,  # already in stop context
                media=visible_media,
                post_type=p.post_type,
                activity_type=p.activity_type,
                summary=p.summary,
                activity_started_at=p.activity_started_at,
                activity_ended_at=p.activity_ended_at,
                poi=poi_out,
            )
        )

    # Siblings (prev/next by sort_order within the same trip)
    siblings_query = (
        select(Stop.slug, Stop.title, Stop.address_label, Stop.sort_order)
        .where(Stop.trip_id == stop.trip_id)
        .order_by(Stop.sort_order.asc())
    )
    siblings_query = siblings_query.where(Stop.status == StopStatus.PUBLISHED)
    if not user:
        siblings_query = siblings_query.where(Stop.visibility == Visibility.PUBLIC)
    sibling_rows = (await session.execute(siblings_query)).all()
    prev_sib = None
    next_sib = None
    for i, row in enumerate(sibling_rows):
        if row.slug == stop.slug:
            if i > 0:
                prev_sib = PublicStopSibling(
                    slug=sibling_rows[i - 1].slug,
                    title=sibling_rows[i - 1].title,
                    address_label=sibling_rows[i - 1].address_label,
                )
            if i + 1 < len(sibling_rows):
                next_sib = PublicStopSibling(
                    slug=sibling_rows[i + 1].slug,
                    title=sibling_rows[i + 1].title,
                    address_label=sibling_rows[i + 1].address_label,
                )
            break

    return PublicStopDetail(
        id=stop.id,
        trip_id=stop.trip_id,
        slug=stop.slug,
        title=stop.title,
        summary=stop.summary,
        place_name=stop.place_name,
        address_label=stop.address_label,
        start_date=stop.start_date,
        end_date=stop.end_date,
        nights=stop.nights,
        status=stop.status,
        sort_order=stop.sort_order,
        latitude=latitude,
        longitude=longitude,
        rv_features=stop.rv_features or [],
        miles_from_previous=stop.miles_from_previous,
        estimated_travel_time=stop.estimated_travel_time,
        public_note=stop.public_note,
        cover_media=visible_ready_cover_media(stop.cover_media, user),
        body=stop.body,
        trip_slug=stop.trip.slug,
        trip_title=stop.trip.title,
        timezone_id=stop.timezone_id,
        media=own_media,
        posts=posts_out,
        pois=pois_out,
        media_with_gps=media_gps_out,
        prev=prev_sib,
        next=next_sib,
    )


@router.get("/{trip_slug}/stops/{stop_slug}/posts/{post_slug}", response_model=PublicPostDetail)
async def get_post(
    trip_slug: str,
    stop_slug: str,
    post_slug: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user_optional),
):
    query = (
        select(Post)
        .join(Stop, Post.stop_id == Stop.id)
        .join(Trip, Stop.trip_id == Trip.id)
        .where(Trip.slug == trip_slug, Stop.slug == stop_slug, Post.slug == post_slug)
        .options(
            selectinload(Post.media),
            selectinload(Post.poi),
            selectinload(Post.stop).selectinload(Stop.trip),
        )
    )
    query = query.where(
        Trip.status == TripStatus.PUBLISHED,
        Stop.status == StopStatus.PUBLISHED,
        Post.status == PostStatus.PUBLISHED,
    )
    if not user:
        query = query.where(
            Trip.visibility == Visibility.PUBLIC,
            Stop.visibility == Visibility.PUBLIC,
            Post.visibility == Visibility.PUBLIC,
        )
    post = (await session.execute(query)).scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    stop = post.stop
    trip = stop.trip

    poi_out = None
    if post.poi:
        coords_map = await _batch_poi_coords(session, [post.poi.id])
        coords = coords_map.get(post.poi.id, (0.0, 0.0))
        poi_out = PublicPOISummary(
            id=post.poi.id,
            label=post.poi.label,
            poi_type=post.poi.poi_type.value,
            google_maps_url=post.poi.google_maps_url,
            latitude=coords[0],
            longitude=coords[1],
        )

    visible_media = visible_ready_media(post.media or [], user)

    # Global post siblings ordered by post date, regardless of stop or trip.
    post_siblings_query = (
        select(
            Post.id,
            Post.slug,
            Post.title,
            Post.posted_at,
            Stop.slug.label("stop_slug"),
            Trip.slug.label("trip_slug"),
        )
        .join(Stop, Post.stop_id == Stop.id)
        .join(Trip, Stop.trip_id == Trip.id)
        .where(
            Trip.status == TripStatus.PUBLISHED,
            Stop.status == StopStatus.PUBLISHED,
            Post.status == PostStatus.PUBLISHED,
        )
        .order_by(Post.posted_at.asc(), Post.id.asc())
    )
    if not user:
        post_siblings_query = post_siblings_query.where(
            Trip.visibility == Visibility.PUBLIC,
            Stop.visibility == Visibility.PUBLIC,
            Post.visibility == Visibility.PUBLIC,
        )
    post_sibling_rows = (await session.execute(post_siblings_query)).all()
    prev_post = None
    next_post = None
    for i, row in enumerate(post_sibling_rows):
        if row.id == post.id:
            if i > 0:
                prev_post = PublicPostSibling(
                    slug=post_sibling_rows[i - 1].slug,
                    title=post_sibling_rows[i - 1].title,
                    stop_slug=post_sibling_rows[i - 1].stop_slug,
                    trip_slug=post_sibling_rows[i - 1].trip_slug,
                )
            if i + 1 < len(post_sibling_rows):
                next_post = PublicPostSibling(
                    slug=post_sibling_rows[i + 1].slug,
                    title=post_sibling_rows[i + 1].title,
                    stop_slug=post_sibling_rows[i + 1].stop_slug,
                    trip_slug=post_sibling_rows[i + 1].trip_slug,
                )
            break

    # Prev/next activity siblings on the same stop, ordered by activity_started_at
    prev_activity = None
    next_activity = None
    if post.post_type == PostType.ACTIVITY:
        sib_q = (
            select(Post.slug, Post.title, Post.activity_started_at, Post.posted_at)
            .where(Post.stop_id == stop.id, Post.post_type == PostType.ACTIVITY)
            .order_by(func.coalesce(Post.activity_started_at, Post.posted_at).asc())
        )
        sib_q = sib_q.where(Post.status == PostStatus.PUBLISHED)
        if not user:
            sib_q = sib_q.where(Post.visibility == Visibility.PUBLIC)
        sib_rows = (await session.execute(sib_q)).all()
        for i, row in enumerate(sib_rows):
            if row.slug == post.slug:
                if i > 0:
                    prev_activity = PublicPostSibling(
                        slug=sib_rows[i - 1].slug,
                        title=sib_rows[i - 1].title,
                        stop_slug=stop.slug,
                        trip_slug=trip.slug,
                    )
                if i + 1 < len(sib_rows):
                    next_activity = PublicPostSibling(
                        slug=sib_rows[i + 1].slug,
                        title=sib_rows[i + 1].title,
                        stop_slug=stop.slug,
                        trip_slug=trip.slug,
                    )
                break

    return PublicPostDetail(
        id=post.id,
        slug=post.slug,
        title=post.title,
        body=post.body,
        posted_at=post.posted_at,
        is_featured=post.is_featured,
        stop=None,
        media=visible_media,
        post_type=post.post_type,
        activity_type=post.activity_type,
        summary=post.summary,
        activity_started_at=post.activity_started_at,
        activity_ended_at=post.activity_ended_at,
        poi=poi_out,
        stop_slug=stop.slug,
        stop_title=stop.title,
        stop_place_name=stop.place_name,
        stop_address_label=stop.address_label,
        trip_slug=trip.slug,
        trip_title=trip.title,
        stop_timezone_id=stop.timezone_id,
        prev_activity=prev_activity,
        next_activity=next_activity,
        prev_post=prev_post,
        next_post=next_post,
    )

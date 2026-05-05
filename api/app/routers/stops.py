from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.auth_config import fastapi_users_app
from app.db import get_async_session
from app.models.content import MediaAsset, Post, Stop, Trip
from app.models.enums import Visibility
from app.schemas.journey import (
    PublicPostSummary,
    PublicStopDetail,
    PublicStopSibling,
)

router = APIRouter(prefix="/trips", tags=["stops"])
current_user_optional = fastapi_users_app.current_user(optional=True, active=True)


def _is_admin(user) -> bool:
    return bool(user and getattr(getattr(user, "role", None), "value", None) == "admin")


def _public_or_admin(query, model, user):
    if _is_admin(user):
        return query
    return query.where(model.visibility == Visibility.PUBLIC)


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
        )
    )

    if not _is_admin(user):
        query = query.where(
            Trip.visibility == Visibility.PUBLIC,
            Stop.visibility == Visibility.PUBLIC,
        )

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

    # Own media (assets directly attached to this stop)
    own_media = [
        m for m in (stop.media or [])
        if _is_admin(user) or m.visibility == Visibility.PUBLIC
    ]

    # Posts pinned to this stop
    posts_query = (
        select(Post)
        .where(Post.stop_id == stop.id)
        .options(selectinload(Post.media), selectinload(Post.stop))
        .order_by(Post.posted_at.desc())
    )
    posts_query = _public_or_admin(posts_query, Post, user)
    posts_rows = (await session.execute(posts_query)).scalars().all()
    posts_out: list[PublicPostSummary] = []
    for p in posts_rows:
        visible_media = [
            m for m in (p.media or [])
            if _is_admin(user) or m.visibility == Visibility.PUBLIC
        ]
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
            )
        )

    # Siblings (prev/next by sort_order within the same trip)
    siblings_query = (
        select(Stop.slug, Stop.title, Stop.sort_order)
        .where(Stop.trip_id == stop.trip_id)
        .order_by(Stop.sort_order.asc())
    )
    if not _is_admin(user):
        siblings_query = siblings_query.where(Stop.visibility == Visibility.PUBLIC)
    sibling_rows = (await session.execute(siblings_query)).all()
    prev_sib = None
    next_sib = None
    for i, row in enumerate(sibling_rows):
        if row.slug == stop.slug:
            if i > 0:
                prev_sib = PublicStopSibling(slug=sibling_rows[i - 1].slug, title=sibling_rows[i - 1].title)
            if i + 1 < len(sibling_rows):
                next_sib = PublicStopSibling(slug=sibling_rows[i + 1].slug, title=sibling_rows[i + 1].title)
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
        stop_type=stop.stop_type,
        sort_order=stop.sort_order,
        latitude=latitude,
        longitude=longitude,
        rv_features=stop.rv_features or [],
        miles_from_previous=stop.miles_from_previous,
        estimated_travel_time=stop.estimated_travel_time,
        public_note=stop.public_note,
        cover_media=stop.cover_media if stop.cover_media and (_is_admin(user) or stop.cover_media.visibility == Visibility.PUBLIC) else None,
        body=stop.body,
        trip_slug=stop.trip.slug,
        trip_title=stop.trip.title,
        media=own_media,
        posts=posts_out,
        prev=prev_sib,
        next=next_sib,
    )

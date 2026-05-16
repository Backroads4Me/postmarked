import asyncio
import os
from datetime import datetime, timezone, timedelta

from fastapi_users.password import PasswordHelper
from sqlalchemy import select, update

from app.db import async_session_maker
from app.models.content import Journey, Post, Stop, Trip
from app.models.enums import (
    ApprovalState,
    JourneyStatus,
    StopStatus,
    StopType,
    TripStatus,
    UserRole,
    Visibility,
)
from app.models.profile import RvProfile, TravelerProfile
from app.models.user import User


async def first_or_none(session, model, **filters):
    query = select(model)
    for field, value in filters.items():
        query = query.where(getattr(model, field) == value)
    result = await session.execute(query)
    return result.scalars().first()


async def seed_user(session):
    admin_email = os.getenv("GOODPATH_ADMIN_EMAIL", "admin@example.com").strip().lower()
    admin_password = os.getenv("GOODPATH_ADMIN_PASSWORD", "admin123")
    admin_display_name = os.getenv("GOODPATH_ADMIN_DISPLAY_NAME", "Ted & Family")

    if not admin_email:
        raise RuntimeError("GOODPATH_ADMIN_EMAIL must not be empty")
    if not admin_password:
        raise RuntimeError("GOODPATH_ADMIN_PASSWORD must not be empty")

    password_helper = PasswordHelper()
    existing = await first_or_none(session, User, email=admin_email)
    if existing:
        existing.hashed_password = password_helper.hash(admin_password)
        existing.display_name = existing.display_name or admin_display_name
        existing.role = UserRole.ADMIN
        existing.approval_state = ApprovalState.APPROVED
        existing.is_active = True
        existing.is_superuser = True
        existing.is_verified = True
        return existing

    admin = User(
        email=admin_email,
        hashed_password=password_helper.hash(admin_password),
        display_name=admin_display_name,
        role=UserRole.ADMIN,
        approval_state=ApprovalState.APPROVED,
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    session.add(admin)
    return admin


async def seed_profiles(session):
    if not await first_or_none(session, RvProfile):
        session.add(
            RvProfile(
                title="The Grand Roamer",
                rv_name="Roamer 1",
                make="Newmar",
                model="Bay Star",
                year=2021,
                length_feet=34,
                visibility=Visibility.PUBLIC,
            )
        )
    if not await first_or_none(session, TravelerProfile):
        session.add(
            TravelerProfile(
                title="The Goodpath Family",
                intro="We sold our house to live on wheels. Exploring America one campground at a time.",
                visibility=Visibility.PUBLIC,
            )
        )


async def get_or_create_journey(session):
    journey = await first_or_none(session, Journey, slug="full-time-rv-life")
    if journey:
        return journey

    journey = Journey(
        slug="full-time-rv-life",
        title="Full-Time RV Life",
        summary="Our continuous RV adventure across America.",
        starts_on=(datetime.now(timezone.utc) - timedelta(days=365)).date(),
        status=JourneyStatus.ACTIVE,
        visibility=Visibility.PUBLIC,
        current_location_note="Currently settled in for a few days of trails, groceries, and route planning.",
        published_at=datetime.now(timezone.utc),
    )
    session.add(journey)
    await session.flush()
    return journey


async def get_or_create_trip(session, journey, slug, title, summary, status, start_delta, end_delta=None):
    trip = await first_or_none(session, Trip, slug=slug)
    if not trip:
        trip = Trip(slug=slug, title=title)
        session.add(trip)

    trip.journey_id = journey.id
    trip.title = title
    trip.summary = summary
    trip.start_date = datetime.now(timezone.utc) + start_delta
    trip.end_date = datetime.now(timezone.utc) + end_delta if end_delta else None
    trip.status = status
    trip.visibility = Visibility.PUBLIC
    await session.flush()
    return trip


async def get_or_create_stop(session, **data):
    stop = await first_or_none(session, Stop, slug=data["slug"])
    if not stop:
        stop = Stop(slug=data["slug"], location=data["location"], trip_id=data["trip_id"], title=data["title"], start_date=data["start_date"])
        session.add(stop)

    for key, value in data.items():
        setattr(stop, key, value)
    return stop


async def get_or_create_post(session, **data):
    post = await first_or_none(session, Post, slug=data["slug"])
    if not post:
        post = Post(slug=data["slug"], journey_id=data["journey_id"], title=data["title"], posted_at=data["posted_at"])
        session.add(post)

    for key, value in data.items():
        setattr(post, key, value)
    return post


async def seed():
    async with async_session_maker() as session:
        await seed_user(session)
        await seed_profiles(session)
        journey = await get_or_create_journey(session)

        past_trip = await get_or_create_trip(
            session,
            journey,
            slug="pacific-coast-highway",
            title="Pacific Coast Highway",
            summary="A coastal chapter with redwoods, foggy mornings, and tight campground roads.",
            status=TripStatus.PUBLISHED,
            start_delta=timedelta(days=-60),
            end_delta=timedelta(days=-45),
        )
        active_trip = await get_or_create_trip(
            session,
            journey,
            slug="michigan-ny-2026",
            title="Michigan, NY 2026",
            summary="A live summer route through the Great Lakes and upstate New York.",
            status=TripStatus.ACTIVE,
            start_delta=timedelta(days=-5),
        )

        # Make the demo data deterministic even after manual testing/imports.
        # Only one stop should be "current", and the active demo trip should
        # have one active stop followed by future planned stops.
        await session.execute(update(Stop).values(is_current=False))
        all_stops = (await session.execute(select(Stop))).scalars().all()
        trip_by_id = {
            trip.id: trip
            for trip in (await session.execute(select(Trip))).scalars().all()
        }
        now = datetime.now(timezone.utc)
        for stop in all_stops:
            trip = trip_by_id.get(stop.trip_id)
            if trip and stop.journey_id != trip.journey_id:
                stop.journey_id = trip.journey_id
            if stop.status == StopStatus.ACTIVE:
                stop.status = (
                    StopStatus.PLANNED
                    if stop.start_date and stop.start_date > now
                    else StopStatus.PUBLISHED
                )

        stops = [
            await get_or_create_stop(
                session,
                journey_id=journey.id,
                trip_id=past_trip.id,
                slug="redwood-national-park",
                title="Redwood National Park",
                summary="Among the giants.",
                location="POINT(-124.0046 41.2132)",
                place_name="Redwood National Park, CA",
                start_date=datetime.now(timezone.utc) - timedelta(days=60),
                end_date=datetime.now(timezone.utc) - timedelta(days=56),
                nights=4,
                status=StopStatus.PUBLISHED,
                stop_type=StopType.CAMPGROUND,
                visibility=Visibility.PUBLIC,
                sort_order=1,
                rv_features=["Full hookups", "Big rig access", "Dump station"],
                miles_from_previous=184,
                estimated_travel_time="4h 10m",
                would_stay_again=True,
                public_note="The morning fog through the redwoods was unforgettable.",
            ),
            await get_or_create_stop(
                session,
                journey_id=journey.id,
                trip_id=active_trip.id,
                slug="charlestown-state-park",
                title="Charlestown State Park",
                summary="Beautiful Indiana state park along the Ohio River.",
                location="POINT(-85.64618 38.44927)",
                place_name="Charlestown, IN",
                start_date=datetime.now(timezone.utc) - timedelta(days=5),
                end_date=datetime.now(timezone.utc) + timedelta(days=2),
                nights=7,
                status=StopStatus.ACTIVE,
                stop_type=StopType.CAMPGROUND,
                visibility=Visibility.PUBLIC,
                sort_order=1,
                is_current=True,
                rv_features=["Pets allowed", "Big rig access", "Dump station"],
                public_note="Currently here. Great trails and river views.",
            ),
            await get_or_create_stop(
                session,
                journey_id=journey.id,
                trip_id=active_trip.id,
                slug="illinois-beach-state-park",
                title="Illinois Beach State Park",
                summary="Next up: Lake Michigan shoreline camping.",
                location="POINT(-87.81042 42.43007)",
                place_name="Zion, IL",
                start_date=datetime.now(timezone.utc) + timedelta(days=3),
                end_date=datetime.now(timezone.utc) + timedelta(days=7),
                nights=4,
                status=StopStatus.PLANNED,
                stop_type=StopType.CAMPGROUND,
                visibility=Visibility.PUBLIC,
                sort_order=2,
                rv_features=["Pets allowed", "Big rig access"],
            ),
        ]
        await session.flush()

        current_stop = next((stop for stop in stops if stop.slug == "charlestown-state-park"), None)
        if current_stop:
            journey.current_stop_id = current_stop.id
            current_stop.is_current = True

        await get_or_create_post(
            session,
            journey_id=journey.id,
            trip_id=active_trip.id,
            stop_id=current_stop.id if current_stop else None,
            slug="arrived-charlestown",
            title="Arrived at Charlestown",
            body="Made it to Indiana. The state park is quiet, the site is level, and the Ohio River trails are calling.",
            posted_at=datetime.now(timezone.utc) - timedelta(days=2),
            visibility=Visibility.PUBLIC,
            is_featured=True,
        )
        await get_or_create_post(
            session,
            journey_id=journey.id,
            trip_id=active_trip.id,
            stop_id=current_stop.id if current_stop else None,
            slug="route-planning-lake-michigan",
            title="Planning the Lake Michigan Leg",
            body="We are checking weather, fuel stops, and campground notes before heading toward Illinois Beach.",
            posted_at=datetime.now(timezone.utc) - timedelta(hours=8),
            visibility=Visibility.PUBLIC,
            is_featured=False,
        )

        await session.commit()
        print("Successfully seeded/backfilled Goodpath demo data.")


if __name__ == "__main__":
    asyncio.run(seed())

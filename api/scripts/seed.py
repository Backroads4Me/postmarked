import asyncio
import os
from datetime import datetime, timezone, timedelta

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.db import async_session_maker
from app.models.content import Post, Stop, Trip
from app.models.enums import (
    ApprovalState,
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
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_display_name = os.getenv("ADMIN_DISPLAY_NAME", "Ted & Family")

    if not admin_email:
        raise RuntimeError("ADMIN_EMAIL must not be empty")
    if not admin_password:
        raise RuntimeError("ADMIN_PASSWORD must not be empty")

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
                title="Backroads 4 Me",
                intro="We sold our house to live on wheels. Exploring America one campground at a time.",
                visibility=Visibility.PUBLIC,
            )
        )


async def get_or_create_trip(session, slug, title, summary, status, start_delta, end_delta=None):
    trip = await first_or_none(session, Trip, slug=slug)
    if not trip:
        trip = Trip(slug=slug, title=title)
        session.add(trip)

    trip.title = title
    trip.summary = summary
    trip.start_date = datetime.now(timezone.utc) + start_delta
    trip.end_date = datetime.now(timezone.utc) + end_delta if end_delta else None
    trip.status = status
    trip.visibility = Visibility.PUBLIC
    await session.flush()
    return trip


async def get_or_create_stop(session, **data):
    stop = await first_or_none(session, Stop, trip_id=data["trip_id"], slug=data["slug"])
    if not stop:
        stop = Stop(slug=data["slug"], location=data["location"], trip_id=data["trip_id"], title=data["title"], start_date=data["start_date"])
        session.add(stop)

    for key, value in data.items():
        setattr(stop, key, value)
    return stop


async def get_or_create_post(session, **data):
    post = await first_or_none(session, Post, slug=data["slug"])
    if not post:
        post = Post(slug=data["slug"], title=data["title"], posted_at=data["posted_at"])
        session.add(post)

    for key, value in data.items():
        setattr(post, key, value)
    return post


async def seed():
    async with async_session_maker() as session:
        await seed_user(session)
        await seed_profiles(session)

        past_trip = await get_or_create_trip(
            session,
            slug="pacific-coast-highway",
            title="Pacific Coast Highway",
            summary="A coastal chapter with redwoods, foggy mornings, and tight campground roads.",
            status=TripStatus.PUBLISHED,
            start_delta=timedelta(days=-60),
            end_delta=timedelta(days=-45),
        )
        active_trip = await get_or_create_trip(
            session,
            slug="michigan-ny-2026",
            title="Michigan, NY 2026",
            summary="A live summer route through the Great Lakes and upstate New York.",
            status=TripStatus.PUBLISHED,
            start_delta=timedelta(days=-5),
        )

        await get_or_create_stop(
            session,
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
        )

        current_stop = await get_or_create_stop(
            session,
            trip_id=active_trip.id,
            slug="charlestown-state-park",
            title="Charlestown State Park",
            summary="Beautiful Indiana state park along the Ohio River.",
            location="POINT(-85.64618 38.44927)",
            place_name="Charlestown, IN",
            start_date=datetime.now(timezone.utc) - timedelta(days=5),
            end_date=datetime.now(timezone.utc) + timedelta(days=2),
            nights=7,
            status=StopStatus.PUBLISHED,
            stop_type=StopType.CAMPGROUND,
            visibility=Visibility.PUBLIC,
            sort_order=1,
            is_current=True,
            rv_features=["Pets allowed", "Big rig access", "Dump station"],
            public_note="Currently here. Great trails and river views.",
        )

        await get_or_create_stop(
            session,
            trip_id=active_trip.id,
            slug="illinois-beach-state-park",
            title="Illinois Beach State Park",
            summary="Next up: Lake Michigan shoreline camping.",
            location="POINT(-87.81042 42.43007)",
            place_name="Zion, IL",
            start_date=datetime.now(timezone.utc) + timedelta(days=3),
            end_date=datetime.now(timezone.utc) + timedelta(days=7),
            nights=4,
            status=StopStatus.PUBLISHED,
            stop_type=StopType.CAMPGROUND,
            visibility=Visibility.PUBLIC,
            sort_order=2,
            rv_features=["Pets allowed", "Big rig access"],
        )

        await session.flush()

        await get_or_create_post(
            session,
            trip_id=active_trip.id,
            stop_id=current_stop.id,
            slug="arrived-charlestown",
            title="Arrived at Charlestown",
            body="Made it to Indiana. The state park is quiet, the site is level, and the Ohio River trails are calling.",
            posted_at=datetime.now(timezone.utc) - timedelta(days=2),
            visibility=Visibility.PUBLIC,
            is_featured=True,
        )
        await get_or_create_post(
            session,
            trip_id=active_trip.id,
            stop_id=current_stop.id,
            slug="route-planning-lake-michigan",
            title="Planning the Lake Michigan Leg",
            body="We are checking weather, fuel stops, and campground notes before heading toward Illinois Beach.",
            posted_at=datetime.now(timezone.utc) - timedelta(hours=8),
            visibility=Visibility.PUBLIC,
            is_featured=False,
        )

        await session.commit()
        print("Successfully seeded/backfilled Postmarked demo data.")


if __name__ == "__main__":
    asyncio.run(seed())

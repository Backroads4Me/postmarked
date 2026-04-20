import asyncio
import os
from datetime import datetime, timezone, timedelta
from app.db import async_session_maker
from app.models.user import User
from app.models.content import Trip, Stop, MediaAsset
from app.models.profile import RvProfile, TravelerProfile
from app.models.enums import Visibility, UserRole, ApprovalState, TripStatus, StopStatus, StopType, MediaKind, MediaProcessingState
from fastapi_users.password import PasswordHelper
from sqlalchemy import select

async def seed():
    async with async_session_maker() as session:
        # Check if already seeded
        result = await session.execute(select(User))
        if result.scalars().first():
            print("Database already seeded. Skipping.")
            return

        password_helper = PasswordHelper()
        hashed_password = password_helper.hash("admin123")
        
        # 1. User
        admin = User(
            email="admin@example.com",
            hashed_password=hashed_password,
            display_name="Admin Traveler",
            role=UserRole.ADMIN,
            approval_state=ApprovalState.APPROVED,
            is_active=True,
            is_superuser=True,
            is_verified=True,
        )
        session.add(admin)
        
        # 2. Profiles
        rv = RvProfile(
            title="The Grand Roamer",
            rv_name="Roamer 1",
            make="Airstream",
            model="Flying Cloud",
            year=2021,
            length_feet=25,
            visibility=Visibility.PUBLIC
        )
        traveler = TravelerProfile(
            title="Wandering Couple",
            intro="We sold our house to live on wheels.",
            visibility=Visibility.PUBLIC
        )
        session.add_all([rv, traveler])
        
        # 3. Trips
        trip1 = Trip(
            slug="pacific-coast-highway",
            title="Pacific Coast Highway",
            summary="A beautiful drive down the coast of California.",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc) - timedelta(days=20),
            status=TripStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        trip2 = Trip(
            slug="rocky-mountains",
            title="Rocky Mountain High",
            summary="Exploring the peaks and valleys.",
            start_date=datetime.now(timezone.utc) - timedelta(days=10),
            status=TripStatus.ACTIVE,
            visibility=Visibility.PRIVATE, # Private trip!
        )
        session.add_all([trip1, trip2])
        await session.flush()
        
        # 4. Stops
        stop1 = Stop(
            trip_id=trip1.id,
            slug="redwood-national-park",
            title="Redwood National Park",
            summary="Among the giants.",
            location="POINT(-124.0046 41.2132)", # longitude, latitude
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc) - timedelta(days=28),
            status=StopStatus.PUBLISHED,
            stop_type=StopType.CAMPGROUND,
            visibility=Visibility.PUBLIC,
            sort_order=1
        )
        stop2 = Stop(
            trip_id=trip1.id,
            slug="secret-beach-cove",
            title="Secret Beach Cove",
            summary="A quick overnight boondock.",
            location="POINT(-124.1 41.0)",
            start_date=datetime.now(timezone.utc) - timedelta(days=28),
            status=StopStatus.ARCHIVED,
            stop_type=StopType.BOONDOCKING,
            visibility=Visibility.PRIVATE,
            sort_order=2
        )
        
        stop3 = Stop(
            trip_id=trip2.id,
            slug="estespark",
            title="Estes Park Basecamp",
            summary="Getting ready to head into rmnp.",
            location="POINT(-105.5217 40.3772)",
            start_date=datetime.now(timezone.utc) - timedelta(days=10),
            status=StopStatus.ACTIVE,
            stop_type=StopType.CAMPGROUND,
            visibility=Visibility.PRIVATE,
            sort_order=1
        )
        
        session.add_all([stop1, stop2, stop3])
        
        await session.commit()
        print("Successfully seeded the database.")

if __name__ == "__main__":
    asyncio.run(seed())

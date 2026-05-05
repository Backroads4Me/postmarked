"""
Admin-side schemas for managing Journey rows.

Public-side schemas live in app.schemas.journey (PublicJourneySummary etc.)
and intentionally don't expose status / visibility for non-admins.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import JourneyStatus, Visibility
from app.schemas.common import BaseResponse


class JourneyAdminOut(BaseResponse):
    id: uuid.UUID
    slug: str
    title: str
    summary: Optional[str] = None
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    status: JourneyStatus
    visibility: Visibility
    current_stop_id: Optional[uuid.UUID] = None
    current_location_note: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class JourneyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: Optional[str] = None  # auto-generated from title when omitted
    summary: Optional[str] = Field(default=None, max_length=10000)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    status: JourneyStatus = JourneyStatus.ACTIVE
    visibility: Visibility = Visibility.PUBLIC
    current_location_note: Optional[str] = None


class JourneyUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    summary: Optional[str] = Field(default=None, max_length=10000)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    status: Optional[JourneyStatus] = None
    visibility: Optional[Visibility] = None
    current_location_note: Optional[str] = None

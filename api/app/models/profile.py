import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.enums import Visibility


class RvProfile(Base):
    __tablename__ = "rv_profile"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PUBLIC)
    
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rv_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    make: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rv_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    length_feet: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    setup_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    towing_info: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    modifications: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    cover_media_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("media_asset.id", ondelete="SET NULL", use_alter=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TravelerProfile(Base):
    __tablename__ = "traveler_profile"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PUBLIC)
    
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    intro: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    story: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    travel_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    family_info: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pet_info: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    contact_links: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    cover_media_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("media_asset.id", ondelete="SET NULL", use_alter=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

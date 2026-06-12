from datetime import datetime
import uuid
from typing import Optional
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SqlaEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import UserRole, ApprovalState, NotificationFrequency

class User(SQLAlchemyBaseUserTableUUID, Base):
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(SqlaEnum(UserRole, name="userrole"), default=UserRole.USER)
    approval_state: Mapped[ApprovalState] = mapped_column(SqlaEnum(ApprovalState, name="approvalstate"), default=ApprovalState.PENDING)
    
    # We can override standard fields if needed, but the base provides email, hashed_password, is_active, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    notification_preference: Mapped["NotificationPreference"] = relationship("NotificationPreference", back_populates="user", uselist=False)


class NotificationPreference(Base):
    __tablename__ = "notification_preference"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), unique=True)
    frequency: Mapped[NotificationFrequency] = mapped_column(SqlaEnum(NotificationFrequency, name="notificationfrequency"), default=NotificationFrequency.ALL_UPDATES)
    email_opted_in: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    unsubscribed_token: Mapped[str] = mapped_column(String, nullable=False, unique=True, default=lambda: uuid.uuid4().hex)

    user: Mapped["User"] = relationship("User", back_populates="notification_preference")

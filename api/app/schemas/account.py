from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import ApprovalState, NotificationFrequency, UserRole


class AccountOut(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None
    role: UserRole
    approval_state: ApprovalState
    notification_frequency: NotificationFrequency


class ProfileUpdate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = Field(default=None, max_length=200)


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class NotificationUpdate(BaseModel):
    notification_frequency: NotificationFrequency

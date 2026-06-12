from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import ApprovalState, NotificationFrequency, UserRole


class AccountOut(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None
    role: UserRole
    approval_state: ApprovalState
    email_opted_in: bool = False
    notification_frequency: NotificationFrequency


class ProfileUpdate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = Field(default=None, max_length=200)
    current_password: str = Field(min_length=1)


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class NotificationUpdate(BaseModel):
    email_opted_in: bool = False
    notification_frequency: NotificationFrequency = NotificationFrequency.ALL_UPDATES

    @field_validator("notification_frequency")
    @classmethod
    def validate_frequency(cls, v: NotificationFrequency) -> NotificationFrequency:
        from app.schemas.user import PUBLIC_NOTIFICATION_FREQUENCIES

        if v not in PUBLIC_NOTIFICATION_FREQUENCIES:
            raise ValueError("Unsupported notification frequency")
        return v

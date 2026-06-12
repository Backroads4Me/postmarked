import uuid
from typing import Optional

from fastapi_users import schemas
from pydantic import field_validator

from app.models.enums import ApprovalState, UserRole
from app.models.enums import NotificationFrequency


PUBLIC_NOTIFICATION_FREQUENCIES = {
    NotificationFrequency.ALL_UPDATES,
    NotificationFrequency.WEEKLY_DIGEST,
}


class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: Optional[str] = None
    avatar_path: Optional[str] = None
    role: UserRole
    approval_state: ApprovalState


class UserCreate(schemas.BaseUserCreate):
    display_name: Optional[str] = None
    email_opted_in: bool = False
    notification_frequency: Optional[NotificationFrequency] = NotificationFrequency.ALL_UPDATES

    @field_validator("notification_frequency")
    @classmethod
    def validate_public_frequency(cls, value):
        if value is not None and value not in PUBLIC_NOTIFICATION_FREQUENCIES:
            raise ValueError("Unsupported notification frequency")
        return value

    def create_update_dict(self):
        data = super().create_update_dict()
        data.pop("email_opted_in", None)
        data.pop("notification_frequency", None)
        return data

    def create_update_dict_superuser(self):
        data = super().create_update_dict_superuser()
        data.pop("email_opted_in", None)
        data.pop("notification_frequency", None)
        return data


class UserUpdate(schemas.BaseUserUpdate):
    display_name: Optional[str] = None
    avatar_path: Optional[str] = None

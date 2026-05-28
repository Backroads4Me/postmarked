import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import ApprovalState, NotificationFrequency, UserRole

_DIGITS_RE = re.compile(r"^\d{10}$")


class AccountOut(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None
    role: UserRole
    approval_state: ApprovalState
    email_opted_in: bool = False
    notification_frequency: NotificationFrequency
    phone_number: Optional[str] = None
    sms_opted_in: bool = False


class ProfileUpdate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = Field(default=None, max_length=200)


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


def _clean_phone(v: Optional[str]) -> Optional[str]:
    if v is None or v.strip() == "":
        return None
    digits = re.sub(r"\D", "", v.strip())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if not _DIGITS_RE.match(digits):
        raise ValueError("Enter a 10-digit US phone number (e.g. 5551234567)")
    return digits


class NotificationUpdate(BaseModel):
    email_opted_in: bool = False
    notification_frequency: NotificationFrequency = NotificationFrequency.ALL_UPDATES
    phone_number: Optional[str] = Field(default=None, max_length=20)
    sms_opted_in: bool = False

    @field_validator("notification_frequency")
    @classmethod
    def validate_frequency(cls, v: NotificationFrequency) -> NotificationFrequency:
        from app.schemas.user import PUBLIC_NOTIFICATION_FREQUENCIES
        if v not in PUBLIC_NOTIFICATION_FREQUENCIES:
            raise ValueError("Unsupported notification frequency")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _clean_phone(v)


class SmsUpdate(BaseModel):
    phone_number: Optional[str] = Field(default=None, max_length=20)
    sms_opted_in: bool = False

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _clean_phone(v)

import uuid
from typing import Optional

from fastapi_users import schemas

from app.models.enums import ApprovalState, UserRole


class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: Optional[str] = None
    avatar_path: Optional[str] = None
    role: UserRole
    approval_state: ApprovalState


class UserCreate(schemas.BaseUserCreate):
    display_name: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate):
    display_name: Optional[str] = None
    avatar_path: Optional[str] = None

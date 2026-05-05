from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.visibility import ALLOWED_TARGET_KINDS

COMMENT_BODY_MAX_LEN = 2000


class CommentBase(BaseModel):
    target_kind: str
    target_id: uuid.UUID
    body: str

    @field_validator("target_kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        if v not in ALLOWED_TARGET_KINDS:
            raise ValueError(
                f"target_kind must be one of {sorted(ALLOWED_TARGET_KINDS)}"
            )
        return v


class CommentCreate(CommentBase):
    body: str = Field(min_length=1, max_length=COMMENT_BODY_MAX_LEN)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_kind: str
    target_id: uuid.UUID
    body: str
    author_id: uuid.UUID
    author_display_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LikeToggle(BaseModel):
    target_kind: str
    target_id: uuid.UUID

    @field_validator("target_kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        if v not in ALLOWED_TARGET_KINDS:
            raise ValueError(
                f"target_kind must be one of {sorted(ALLOWED_TARGET_KINDS)}"
            )
        return v

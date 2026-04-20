from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime

class CommentBase(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    body_markdown: str

class CommentCreate(CommentBase):
    pass

class CommentOut(CommentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_moderated: bool
    
    class Config:
        from_attributes = True

class LikeToggle(BaseModel):
    entity_type: str
    entity_id: uuid.UUID

from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import uuid

class SearchResult(BaseModel):
    entity_type: str
    id: uuid.UUID
    title: str
    summary: Optional[str]
    slug: str
    start_date: Optional[datetime] = None


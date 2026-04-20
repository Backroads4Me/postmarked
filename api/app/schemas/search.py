from pydantic import BaseModel
from typing import Optional, List
import uuid

class SearchResult(BaseModel):
    entity_type: str
    id: uuid.UUID
    title: str
    summary: Optional[str]
    slug: str

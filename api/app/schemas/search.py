import uuid
from datetime import datetime

from pydantic import BaseModel


class SearchResult(BaseModel):
    entity_type: str
    id: uuid.UUID
    title: str
    summary: str | None
    slug: str
    start_date: datetime | None = None


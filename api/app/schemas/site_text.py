import uuid
from typing import Optional

from pydantic import BaseModel


class SiteTextSectionBase(BaseModel):
    page_key: str
    section_key: str
    label: Optional[str] = None
    heading: str
    body: Optional[str] = None
    cta_label: Optional[str] = None
    cta_href: Optional[str] = None
    sort_order: int = 0


class SiteTextSectionOut(SiteTextSectionBase):
    id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


class SiteTextSectionUpdate(BaseModel):
    label: Optional[str] = None
    heading: str
    body: Optional[str] = None
    cta_label: Optional[str] = None
    cta_href: Optional[str] = None

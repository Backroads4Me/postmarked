import uuid

from pydantic import BaseModel


class SiteTextSectionBase(BaseModel):
    page_key: str
    section_key: str
    label: str | None = None
    heading: str
    body: str | None = None
    cta_label: str | None = None
    cta_href: str | None = None
    sort_order: int = 0


class SiteTextSectionOut(SiteTextSectionBase):
    id: uuid.UUID | None = None

    class Config:
        from_attributes = True


class SiteTextSectionUpdate(BaseModel):
    label: str | None = None
    heading: str
    body: str | None = None
    cta_label: str | None = None
    cta_href: str | None = None

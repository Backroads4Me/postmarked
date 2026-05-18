from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db import get_async_session
from app.models.content import SiteTextSection
from app.schemas.site_text import SiteTextSectionOut
from app.services.site_text import DEFAULT_SITE_TEXT_SECTIONS, serialize_site_text_section

router = APIRouter(prefix="/site-text", tags=["site-text"])


@router.get("", response_model=list[SiteTextSectionOut])
async def list_site_text(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(
        select(SiteTextSection).order_by(SiteTextSection.page_key, SiteTextSection.sort_order)
    )
    stored = {
        (section.page_key, section.section_key): section
        for section in result.scalars().all()
    }

    sections = []
    for default in DEFAULT_SITE_TEXT_SECTIONS:
        section = stored.get((default["page_key"], default["section_key"]), default)
        sections.append(serialize_site_text_section(section))
    return sections

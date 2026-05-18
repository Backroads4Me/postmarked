import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_admin_user
from app.db import get_async_session
from app.models.content import SiteTextSection
from app.models.user import User
from app.schemas.site_text import SiteTextSectionOut, SiteTextSectionUpdate
from app.services.audit import log_audit_event
from app.services.site_text import DEFAULT_SITE_TEXT_SECTIONS, serialize_site_text_section

router = APIRouter(prefix="/site-text", tags=["admin-site-text"])


async def _site_text_sections_with_defaults(session: AsyncSession) -> list[SiteTextSectionOut]:
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


@router.get("", response_model=list[SiteTextSectionOut])
async def list_site_text_admin(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    return await _site_text_sections_with_defaults(session)


@router.patch("/{page_key}/{section_key}", response_model=SiteTextSectionOut)
async def update_site_text_section(
    page_key: str,
    section_key: str,
    section_in: SiteTextSectionUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    allowed = next(
        (
            section
            for section in DEFAULT_SITE_TEXT_SECTIONS
            if section["page_key"] == page_key and section["section_key"] == section_key
        ),
        None,
    )
    if not allowed:
        raise HTTPException(status_code=404, detail="Site text section not found")

    section = (
        await session.execute(
            select(SiteTextSection).where(
                SiteTextSection.page_key == page_key,
                SiteTextSection.section_key == section_key,
            )
        )
    ).scalars().first()

    if not section:
        section = SiteTextSection(
            id=uuid.uuid4(),
            page_key=page_key,
            section_key=section_key,
            sort_order=allowed["sort_order"],
        )
        session.add(section)

    update_data = section_in.model_dump()
    for key, value in update_data.items():
        setattr(section, key, value)

    await session.flush()
    await log_audit_event(session, user.id, "UPDATE", "SiteTextSection", section.id, update_data)
    await session.commit()
    await session.refresh(section)
    return section

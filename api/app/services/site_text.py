from app.models.content import SiteTextSection
from app.schemas.site_text import SiteTextSectionOut


DEFAULT_SITE_TEXT_SECTIONS = [
    {
        "page_key": "home",
        "section_key": "header",
        "label": "Welcome to Postmarked",
        "heading": "On the Road",
        "body": "Quick updates from the road — where we are, where we've been, and where we're headed.",
        "sort_order": 10,
    },
    {
        "page_key": "home",
        "section_key": "current",
        "label": "Currently At",
        "heading": "Current Location",
        "body": None,
        "sort_order": 20,
    },
    {
        "page_key": "home",
        "section_key": "next",
        "label": "Next Up",
        "heading": "Next Up",
        "body": None,
        "sort_order": 30,
    },
    {
        "page_key": "home",
        "section_key": "upcoming",
        "label": "Upcoming",
        "heading": "Up Next",
        "body": None,
        "sort_order": 40,
    },
    {
        "page_key": "home",
        "section_key": "updates",
        "label": None,
        "heading": "Latest Updates",
        "body": None,
        "cta_label": "See full timeline",
        "cta_href": "/timeline",
        "sort_order": 50,
    },
    {
        "page_key": "trips",
        "section_key": "header",
        "label": "Journeys",
        "heading": "All Trips",
        "body": "Miles become memories.",
        "sort_order": 10,
    },
    {
        "page_key": "timeline",
        "section_key": "header",
        "label": None,
        "heading": "Timeline",
        "body": "Every stop, story, and moment.",
        "sort_order": 10,
    },
    {
        "page_key": "email",
        "section_key": "post_notification",
        "label": None,
        "heading": "New update from the road",
        "body": "A new update has been posted: {post_title}",
        "cta_label": "See the photos",
        "sort_order": 10,
    },
]


def default_site_text_section(page_key: str, section_key: str) -> dict | None:
    return next(
        (
            section
            for section in DEFAULT_SITE_TEXT_SECTIONS
            if section["page_key"] == page_key and section["section_key"] == section_key
        ),
        None,
    )


def serialize_site_text_section(section: SiteTextSection | dict) -> SiteTextSectionOut:
    if isinstance(section, SiteTextSection):
        return SiteTextSectionOut.model_validate(section)
    return SiteTextSectionOut(**section)

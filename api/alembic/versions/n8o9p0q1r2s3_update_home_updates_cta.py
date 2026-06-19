"""Update home updates CTA label to 'See all updates'.

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-06-18
"""

from typing import Union

from alembic import op


revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, None] = "m7n8o9p0q1r2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE site_text_section
        SET cta_label = 'See all updates'
        WHERE page_key = 'home'
          AND section_key = 'updates'
          AND cta_label = 'See full timeline'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE site_text_section
        SET cta_label = 'See full timeline'
        WHERE page_key = 'home'
          AND section_key = 'updates'
          AND cta_label = 'See all updates'
        """
    )

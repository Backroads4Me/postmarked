"""update home timeline cta text

Revision ID: c7d8e9f0a1b2
Revises: c6d7e8f9a0b1
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE site_text_section
        SET cta_label = 'See full timeline'
        WHERE page_key = 'home'
          AND section_key = 'updates'
          AND (cta_label IS NULL OR cta_label = 'View All')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE site_text_section
        SET cta_label = 'View All'
        WHERE page_key = 'home'
          AND section_key = 'updates'
          AND cta_label = 'See full timeline'
        """
    )

"""add site text sections

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_text_section",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("page_key", sa.String(), nullable=False),
        sa.Column("section_key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("heading", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("cta_label", sa.String(), nullable=True),
        sa.Column("cta_href", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_key", "section_key", name="uq_site_text_section_key"),
    )
    op.create_index("ix_site_text_section_page_key", "site_text_section", ["page_key"])


def downgrade() -> None:
    op.drop_index("ix_site_text_section_page_key", table_name="site_text_section")
    op.drop_table("site_text_section")

"""add site_config and pre_approved_email tables

Revision ID: e6f7a8b9c0d1
Revises: d0e1f2a3b4c5
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_config",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("require_user_approval", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pre_approved_email",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_pre_approved_email"),
    )
    op.create_index("ix_pre_approved_email_email", "pre_approved_email", ["email"])


def downgrade() -> None:
    op.drop_index("ix_pre_approved_email_email", table_name="pre_approved_email")
    op.drop_table("pre_approved_email")
    op.drop_table("site_config")

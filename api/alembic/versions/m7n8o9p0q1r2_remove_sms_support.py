"""Remove SMS notification support.

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-06-12
"""

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, None] = "l6m7n8o9p0q1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_column("notification_preference", "sms_opted_in")
    op.drop_column("notification_preference", "phone_number")
    op.drop_column("site_config", "sms_enabled")


def downgrade() -> None:
    op.add_column(
        "site_config",
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "notification_preference",
        sa.Column("phone_number", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "notification_preference",
        sa.Column("sms_opted_in", sa.Boolean(), nullable=False, server_default="false"),
    )

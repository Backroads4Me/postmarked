"""add sms_enabled to site_config and phone/sms fields to notification_preference

Revision ID: g1h2i3j4k5l6
Revises: f6a7b8c9d0e1
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "site_config",
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "notification_preference",
        sa.Column("phone_number", sa.String(20), nullable=True),
    )
    op.add_column(
        "notification_preference",
        sa.Column("sms_opted_in", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("notification_preference", "sms_opted_in")
    op.drop_column("notification_preference", "phone_number")
    op.drop_column("site_config", "sms_enabled")


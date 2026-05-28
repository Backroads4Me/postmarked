"""add email_opted_in to notification_preference; decouple email on/off from frequency

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_preference",
        sa.Column("email_opted_in", sa.Boolean(), nullable=False, server_default="false"),
    )
    # All existing rows had a real frequency value — 'none' was never a valid
    # PostgreSQL enum label, so every existing user was an email subscriber.
    op.execute("UPDATE notification_preference SET email_opted_in = true")


def downgrade() -> None:
    op.drop_column("notification_preference", "email_opted_in")

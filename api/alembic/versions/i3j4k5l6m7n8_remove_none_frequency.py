"""Remove NONE from notificationfrequency enum; fix email_opted_in for opted-out users

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rows with frequency='NONE' were opted out of email — correct the blanket
    # email_opted_in=true that h2i3j4k5l6m7 applied unconditionally.
    op.execute(
        "UPDATE notification_preference SET email_opted_in = false WHERE frequency::text = 'NONE'"
    )
    # Move opted-out users to ALL_UPDATES (frequency is now a pure timing pref).
    op.execute(
        "UPDATE notification_preference SET frequency = 'ALL_UPDATES' WHERE frequency::text = 'NONE'"
    )

    # Recreate the enum type without the NONE label.
    op.execute(
        "CREATE TYPE notificationfrequency_new AS ENUM "
        "('ALL_UPDATES', 'DAILY_DIGEST', 'WEEKLY_DIGEST', 'MONTHLY_DIGEST')"
    )
    op.execute(
        "ALTER TABLE notification_preference "
        "ALTER COLUMN frequency TYPE notificationfrequency_new "
        "USING frequency::text::notificationfrequency_new"
    )
    op.execute("DROP TYPE notificationfrequency")
    op.execute("ALTER TYPE notificationfrequency_new RENAME TO notificationfrequency")


def downgrade() -> None:
    # Restore NONE label (data loss — opted-out users are not restored).
    op.execute(
        "CREATE TYPE notificationfrequency_new AS ENUM "
        "('ALL_UPDATES', 'DAILY_DIGEST', 'WEEKLY_DIGEST', 'MONTHLY_DIGEST', 'NONE')"
    )
    op.execute(
        "ALTER TABLE notification_preference "
        "ALTER COLUMN frequency TYPE notificationfrequency_new "
        "USING frequency::text::notificationfrequency_new"
    )
    op.execute("DROP TYPE notificationfrequency")
    op.execute("ALTER TYPE notificationfrequency_new RENAME TO notificationfrequency")

"""add unpublished lifecycle status and post status

Revision ID: b1c2d3e4f5a6
Revises: a8b9c0d1e2f3
Create Date: 2026-05-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE tripstatus ADD VALUE IF NOT EXISTS 'UNPUBLISHED'")
    op.execute("ALTER TYPE stopstatus ADD VALUE IF NOT EXISTS 'UNPUBLISHED'")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'poststatus') THEN
                CREATE TYPE poststatus AS ENUM ('draft', 'published', 'unpublished', 'archived');
            END IF;
        END$$;
        """
    )
    op.add_column(
        "post",
        sa.Column(
            "status",
            sa.Enum("draft", "published", "unpublished", "archived", name="poststatus", create_type=False),
            nullable=False,
            server_default="published",
        ),
    )
    op.alter_column("post", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("post", "status")

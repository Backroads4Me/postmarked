"""add indexes on post.stop_id and post.trip_id

Revision ID: d0e1f2a3b4c5
Revises: c7d8e9f0a1b2
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_post_stop_id", "post", ["stop_id"])
    op.create_index("ix_post_trip_id", "post", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_post_trip_id", table_name="post")
    op.drop_index("ix_post_stop_id", table_name="post")

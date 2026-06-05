"""Add folder column to media_asset

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, None] = "i3j4k5l6m7n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media_asset", sa.Column("folder", sa.String(), nullable=True))
    op.create_index("ix_media_asset_folder", "media_asset", ["folder"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_media_asset_folder", table_name="media_asset")
    op.drop_column("media_asset", "folder")

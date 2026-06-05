"""Drop folder column from media_asset

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_media_asset_folder", table_name="media_asset")
    op.drop_column("media_asset", "folder")


def downgrade() -> None:
    op.add_column("media_asset", sa.Column("folder", sa.String(), nullable=True))
    op.create_index("ix_media_asset_folder", "media_asset", ["folder"], unique=False)

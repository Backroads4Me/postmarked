"""remove stop_type column and enum

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-05-24 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('stop', 'stop_type')
    op.execute("DROP TYPE IF EXISTS stoptype")


def downgrade() -> None:
    op.execute(
        "CREATE TYPE stoptype AS ENUM "
        "('CAMPGROUND', 'BOONDOCKING', 'OVERNIGHT', 'ATTRACTION', 'RESTAURANT', 'SERVICE', 'OTHER')"
    )
    op.add_column('stop', sa.Column(
        'stop_type',
        sa.Enum('CAMPGROUND', 'BOONDOCKING', 'OVERNIGHT', 'ATTRACTION', 'RESTAURANT', 'SERVICE', 'OTHER', name='stoptype'),
        nullable=False,
        server_default='OTHER',
    ))

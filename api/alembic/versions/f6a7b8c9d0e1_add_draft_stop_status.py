"""add draft stop status

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE stopstatus ADD VALUE IF NOT EXISTS 'DRAFT' BEFORE 'PLANNED'")


def downgrade() -> None:
    # PostgreSQL enum labels cannot be dropped safely without rebuilding the type.
    pass

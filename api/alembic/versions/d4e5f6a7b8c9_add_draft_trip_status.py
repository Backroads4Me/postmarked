"""add draft trip status

Revision ID: d4e5f6a7b8c9
Revises: c5d6e7f8a9b0
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE tripstatus ADD VALUE IF NOT EXISTS 'DRAFT' BEFORE 'PLANNED'")


def downgrade() -> None:
    # PostgreSQL enum labels cannot be dropped safely without rebuilding the type.
    pass

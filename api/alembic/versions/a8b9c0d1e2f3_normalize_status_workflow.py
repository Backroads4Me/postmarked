"""normalize status workflow

Revision ID: a8b9c0d1e2f3
Revises: f6a7b8c9d0e1
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE stop SET status = 'PUBLISHED' WHERE status IN ('PLANNED', 'ACTIVE')")
    op.execute("UPDATE trip SET status = 'PUBLISHED' WHERE status IN ('PLANNED', 'ACTIVE')")


def downgrade() -> None:
    # The old workflow used PLANNED/ACTIVE ambiguously; restoring it would
    # require business context that is not recoverable from the normalized data.
    pass

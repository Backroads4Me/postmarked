"""Add Journey, ImportRun, PlannedStop, Post models and update Stop

Revision ID: e32e5ce52644
Revises: 3b9f7c2d8a01
Create Date: 2026-05-04 08:51:17.707086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
import fastapi_users_db_sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'e32e5ce52644'
down_revision: Union[str, None] = '3b9f7c2d8a01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK journey.current_stop_id -> stop.id is already created by 3b9f7c2d8a01 via use_alter=True.
    pass


def downgrade() -> None:
    pass

"""Remove journey

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-05-16

"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None

journeystatus = postgresql.ENUM("active", "paused", "archived", name="journeystatus", create_type=False)


def upgrade() -> None:
    # Drop FK constraints from child tables referencing journey
    op.drop_constraint("fk_trip_journey_id_journey", "trip", type_="foreignkey")
    op.drop_constraint("fk_stop_journey_id_journey", "stop", type_="foreignkey")
    op.drop_constraint("post_journey_id_fkey", "post", type_="foreignkey")
    op.drop_constraint("planned_stop_journey_id_fkey", "planned_stop", type_="foreignkey")

    # Drop journey_id columns
    op.drop_column("trip", "journey_id")
    op.drop_column("stop", "journey_id")
    op.drop_column("post", "journey_id")
    op.drop_column("planned_stop", "journey_id")

    # Drop journey table — its own FK (current_stop_id → stop) drops automatically with it
    op.drop_table("journey")

    # Drop journeystatus enum
    bind = op.get_bind()
    journeystatus.drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    journeystatus.create(bind, checkfirst=True)

    op.create_table(
        "journey",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("status", journeystatus, nullable=False, server_default="active"),
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
        sa.Column("current_stop_id", sa.UUID(), nullable=True),
        sa.Column("current_location_note", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_foreign_key(
        "journey_current_stop_id_fkey", "journey", "stop",
        ["current_stop_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column("planned_stop", sa.Column("journey_id", sa.UUID(), nullable=True))
    op.add_column("post", sa.Column("journey_id", sa.UUID(), nullable=True))
    op.add_column("stop", sa.Column("journey_id", sa.UUID(), nullable=True))
    op.add_column("trip", sa.Column("journey_id", sa.UUID(), nullable=True))

    op.create_foreign_key("planned_stop_journey_id_fkey", "planned_stop", "journey", ["journey_id"], ["id"])
    op.create_foreign_key("post_journey_id_fkey", "post", "journey", ["journey_id"], ["id"])
    op.create_foreign_key("fk_stop_journey_id_journey", "stop", "journey", ["journey_id"], ["id"])
    op.create_foreign_key("fk_trip_journey_id_journey", "trip", "journey", ["journey_id"], ["id"])

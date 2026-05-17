"""Add post activities and stop timezone

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-16

"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

posttype = postgresql.ENUM("update", "activity", name="posttype", create_type=False)
activitytype = postgresql.ENUM(
    "hiking", "museum", "restaurant", "attraction", "service",
    "scenic_drive", "shopping", "family", "other",
    name="activitytype", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    posttype.create(bind, checkfirst=True)
    activitytype.create(bind, checkfirst=True)

    # stop: timezone
    op.add_column("stop", sa.Column("timezone_id", sa.String(), nullable=True))

    # post: activity fields
    op.add_column("post", sa.Column("post_type", posttype, nullable=False, server_default="update"))
    op.add_column("post", sa.Column("activity_type", activitytype, nullable=True))
    op.add_column("post", sa.Column("summary", sa.String(), nullable=True))
    op.add_column("post", sa.Column("activity_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("post", sa.Column("activity_ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("post", sa.Column("poi_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_post_poi_id_point_of_interest",
        "post", "point_of_interest",
        ["poi_id"], ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_post_poi_id_point_of_interest", "post", type_="foreignkey")
    op.drop_column("post", "poi_id")
    op.drop_column("post", "activity_ended_at")
    op.drop_column("post", "activity_started_at")
    op.drop_column("post", "summary")
    op.drop_column("post", "activity_type")
    op.drop_column("post", "post_type")
    op.drop_column("stop", "timezone_id")

    bind = op.get_bind()
    posttype.drop(bind, checkfirst=True)
    activitytype.drop(bind, checkfirst=True)

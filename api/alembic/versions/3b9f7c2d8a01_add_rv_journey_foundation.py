"""Add RV journey foundation

Revision ID: 3b9f7c2d8a01
Revises: bf242ca44f6a
Create Date: 2026-05-04 04:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import fastapi_users_db_sqlalchemy


revision: str = "3b9f7c2d8a01"
down_revision: Union[str, None] = "bf242ca44f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


journey_status = postgresql.ENUM("ACTIVE", "PAUSED", "ARCHIVED", name="journeystatus", create_type=False)
planned_stop_import_state = postgresql.ENUM(
    "PLANNED",
    "CHANGED",
    "REMOVED_FROM_LATEST_IMPORT",
    "CONVERTED_TO_STOP",
    name="plannedstopimportstate",
    create_type=False,
)
visibility_type = postgresql.ENUM("PUBLIC", "PRIVATE", name="visibility", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    journey_status.create(bind, checkfirst=True)
    planned_stop_import_state.create(bind, checkfirst=True)

    op.create_table(
        "journey",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("status", journey_status, nullable=False),
        sa.Column("visibility", visibility_type, nullable=False),
        sa.Column("current_stop_id", sa.Uuid(), nullable=True),
        sa.Column("current_location_note", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["current_stop_id"], ["stop.id"], ondelete="SET NULL", use_alter=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_journey_slug"), "journey", ["slug"], unique=True)

    op.create_table(
        "import_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("file_sha256", sa.String(), nullable=False),
        sa.Column("trip_title_from_file", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_by_user_id", fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("trip", sa.Column("journey_id", sa.Uuid(), nullable=True))
    op.add_column("trip", sa.Column("source_kind", sa.String(), nullable=True))
    op.add_column("trip", sa.Column("source_import_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_trip_journey_id_journey", "trip", "journey", ["journey_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_trip_source_import_run_id_import_run", "trip", "import_run", ["source_import_run_id"], ["id"], ondelete="SET NULL")

    op.add_column("stop", sa.Column("journey_id", sa.Uuid(), nullable=True))
    op.add_column("stop", sa.Column("planned_stop_id", sa.Uuid(), nullable=True))
    op.add_column("stop", sa.Column("nights", sa.Integer(), nullable=True))
    op.add_column("stop", sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("stop", sa.Column("rv_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("stop", sa.Column("rv_features", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column("stop", sa.Column("miles_from_previous", sa.Float(), nullable=True))
    op.add_column("stop", sa.Column("estimated_travel_time", sa.String(), nullable=True))
    op.add_column("stop", sa.Column("would_stay_again", sa.Boolean(), nullable=True))
    op.add_column("stop", sa.Column("public_note", sa.String(), nullable=True))
    op.add_column("stop", sa.Column("private_note", sa.String(), nullable=True))
    op.add_column("stop", sa.Column("site_number_private", sa.String(), nullable=True))
    op.add_column("stop", sa.Column("reservation_private", sa.String(), nullable=True))
    op.create_foreign_key("fk_stop_journey_id_journey", "stop", "journey", ["journey_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_stop_is_current"), "stop", ["is_current"], unique=False)

    op.create_table(
        "planned_stop",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journey_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("source_import_run_id", sa.Uuid(), nullable=True),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("source_fingerprint", sa.String(), nullable=False),
        sa.Column("source_sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("arrival_date", sa.Date(), nullable=True),
        sa.Column("departure_date", sa.Date(), nullable=True),
        sa.Column("nights", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("features_raw", sa.String(), nullable=True),
        sa.Column("features", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("comments_private", sa.String(), nullable=True),
        sa.Column("reservation_private", sa.String(), nullable=True),
        sa.Column("miles_from_previous", sa.Float(), nullable=True),
        sa.Column("total_miles", sa.Float(), nullable=True),
        sa.Column("estimated_travel_time", sa.String(), nullable=True),
        sa.Column("camping_cost", sa.Float(), nullable=True),
        sa.Column("meals_cost", sa.Float(), nullable=True),
        sa.Column("misc_cost", sa.Float(), nullable=True),
        sa.Column("fuel_cost", sa.Float(), nullable=True),
        sa.Column("stop_total_cost", sa.Float(), nullable=True),
        sa.Column("starting_fuel", sa.Float(), nullable=True),
        sa.Column("fuel_used", sa.Float(), nullable=True),
        sa.Column("arrival_fuel", sa.Float(), nullable=True),
        sa.Column("fuel_added", sa.Float(), nullable=True),
        sa.Column("departure_fuel", sa.Float(), nullable=True),
        sa.Column("import_state", planned_stop_import_state, nullable=False),
        sa.Column("matched_stop_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["journey_id"], ["journey.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trip.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_import_run_id"], ["import_run.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_stop_id"], ["stop.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_planned_stop_source_fingerprint"), "planned_stop", ["source_fingerprint"], unique=False)
    op.create_foreign_key("fk_stop_planned_stop_id_planned_stop", "stop", "planned_stop", ["planned_stop_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "post",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journey_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=True),
        sa.Column("stop_id", sa.Uuid(), nullable=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visibility", visibility_type, nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["journey_id"], ["journey.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trip.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["stop_id"], ["stop.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_slug"), "post", ["slug"], unique=True)

    op.add_column("media_asset", sa.Column("post_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_media_asset_post_id_post", "media_asset", "post", ["post_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_media_asset_post_id_post", "media_asset", type_="foreignkey")
    op.drop_column("media_asset", "post_id")
    op.drop_index(op.f("ix_post_slug"), table_name="post")
    op.drop_table("post")
    op.drop_constraint("fk_stop_planned_stop_id_planned_stop", "stop", type_="foreignkey")
    op.drop_index(op.f("ix_planned_stop_source_fingerprint"), table_name="planned_stop")
    op.drop_table("planned_stop")
    op.drop_constraint("fk_stop_journey_id_journey", "stop", type_="foreignkey")
    op.drop_index(op.f("ix_stop_is_current"), table_name="stop")
    op.drop_column("stop", "reservation_private")
    op.drop_column("stop", "site_number_private")
    op.drop_column("stop", "private_note")
    op.drop_column("stop", "public_note")
    op.drop_column("stop", "would_stay_again")
    op.drop_column("stop", "estimated_travel_time")
    op.drop_column("stop", "miles_from_previous")
    op.drop_column("stop", "rv_features")
    op.drop_column("stop", "rv_details")
    op.drop_column("stop", "is_current")
    op.drop_column("stop", "nights")
    op.drop_column("stop", "planned_stop_id")
    op.drop_column("stop", "journey_id")
    op.drop_constraint("fk_trip_source_import_run_id_import_run", "trip", type_="foreignkey")
    op.drop_constraint("fk_trip_journey_id_journey", "trip", type_="foreignkey")
    op.drop_column("trip", "source_import_run_id")
    op.drop_column("trip", "source_kind")
    op.drop_column("trip", "journey_id")
    op.drop_table("import_run")
    op.drop_index(op.f("ix_journey_slug"), table_name="journey")
    op.drop_table("journey")

    bind = op.get_bind()
    planned_stop_import_state.drop(bind, checkfirst=True)
    journey_status.drop(bind, checkfirst=True)

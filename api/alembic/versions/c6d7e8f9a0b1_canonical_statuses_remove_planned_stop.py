"""canonical statuses and remove planned stops

Revision ID: c6d7e8f9a0b1
Revises: b1c2d3e4f5a6
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rebuild_status_enum(table_name: str, type_name: str, mapping_sql: str) -> None:
    new_type = f"{type_name}_new"
    op.execute(f"CREATE TYPE {new_type} AS ENUM ('draft', 'published', 'unpublished', 'archived')")
    op.execute(f"ALTER TABLE {table_name} ALTER COLUMN status DROP DEFAULT")
    op.execute(
        f"""
        ALTER TABLE {table_name}
        ALTER COLUMN status TYPE {new_type}
        USING ({mapping_sql})::{new_type}
        """
    )
    op.execute(f"ALTER TABLE {table_name} ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute(f"DROP TYPE {type_name}")
    op.execute(f"ALTER TYPE {new_type} RENAME TO {type_name}")


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM site_text_section planned
        USING site_text_section upcoming
        WHERE planned.page_key = 'home'
          AND planned.section_key = 'planned'
          AND upcoming.page_key = 'home'
          AND upcoming.section_key = 'upcoming'
        """
    )
    op.execute(
        """
        UPDATE site_text_section
        SET section_key = 'upcoming',
            label = COALESCE(NULLIF(label, 'From the trip plan'), 'Upcoming')
        WHERE page_key = 'home' AND section_key = 'planned'
        """
    )

    op.execute("ALTER TABLE stop DROP CONSTRAINT IF EXISTS fk_stop_planned_stop_id_planned_stop")
    op.execute("ALTER TABLE stop DROP COLUMN IF EXISTS planned_stop_id")
    op.execute("DROP TABLE IF EXISTS planned_stop CASCADE")
    op.execute("DROP TYPE IF EXISTS plannedstopimportstate")

    _rebuild_status_enum(
        "trip",
        "tripstatus",
        """
        CASE status::text
            WHEN 'DRAFT' THEN 'draft'
            WHEN 'PLANNED' THEN 'published'
            WHEN 'ACTIVE' THEN 'published'
            WHEN 'COMPLETED' THEN 'published'
            WHEN 'PUBLISHED' THEN 'published'
            WHEN 'UNPUBLISHED' THEN 'unpublished'
            WHEN 'ARCHIVED' THEN 'archived'
            ELSE lower(status::text)
        END
        """,
    )
    _rebuild_status_enum(
        "stop",
        "stopstatus",
        """
        CASE status::text
            WHEN 'DRAFT' THEN 'draft'
            WHEN 'PLANNED' THEN 'published'
            WHEN 'ACTIVE' THEN 'published'
            WHEN 'PUBLISHED' THEN 'published'
            WHEN 'UNPUBLISHED' THEN 'unpublished'
            WHEN 'ARCHIVED' THEN 'archived'
            ELSE lower(status::text)
        END
        """,
    )


def downgrade() -> None:
    # The removed planned_stop table was legacy import storage. Recreating it
    # would not restore dropped rows, so this migration is intentionally forward-only.
    pass

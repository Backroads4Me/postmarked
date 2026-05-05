"""S1 security constraints: per-trip stop slug, like uniqueness, length_feet decimal

Revision ID: a1b2c3d4e5f6
Revises: e32e5ce52644
Create Date: 2026-05-04 12:00:00.000000

Sprint 1 schema hardening from docs/path-to-testing.md:
- T-008: UniqueConstraint(trip_id, slug) on stop
- T-009: UniqueConstraint(author_id, target_kind, target_id) on like
- T-010: rv_profile.length_feet INTEGER -> NUMERIC(5, 1) so half-foot lengths
        (34.5 ft) round-trip without silent truncation.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e32e5ce52644"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T-009: dedupe likes before adding the constraint. Keeps the oldest row.
    op.execute(
        """
        DELETE FROM "like" a
        USING "like" b
        WHERE a.author_id = b.author_id
          AND a.target_kind = b.target_kind
          AND a.target_id = b.target_id
          AND a.created_at > b.created_at
        """
    )
    op.create_unique_constraint(
        "uq_like_author_target",
        "like",
        ["author_id", "target_kind", "target_id"],
    )

    # T-008: dedupe stops with the same (trip_id, slug) before constraint.
    # Suffix later duplicates with a short id fragment so they remain addressable.
    op.execute(
        """
        UPDATE stop SET slug = slug || '-' || substring(id::text, 1, 8)
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY trip_id, slug ORDER BY created_at
                ) AS rn
                FROM stop
            ) t WHERE rn > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_stop_trip_slug",
        "stop",
        ["trip_id", "slug"],
    )

    # T-010: widen length_feet to NUMERIC(5, 1).
    op.alter_column(
        "rv_profile",
        "length_feet",
        existing_type=sa.Integer(),
        type_=sa.Numeric(5, 1),
        existing_nullable=True,
        postgresql_using="length_feet::numeric(5,1)",
    )


def downgrade() -> None:
    op.alter_column(
        "rv_profile",
        "length_feet",
        existing_type=sa.Numeric(5, 1),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="length_feet::integer",
    )
    op.drop_constraint("uq_stop_trip_slug", "stop", type_="unique")
    op.drop_constraint("uq_like_author_target", "like", type_="unique")

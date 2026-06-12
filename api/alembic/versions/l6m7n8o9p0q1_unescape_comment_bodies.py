"""Unescape stored comment bodies.

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-06-12
"""

from typing import Union

from alembic import op


revision: str = "l6m7n8o9p0q1"
down_revision: Union[str, None] = "k5l6m7n8o9p0"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE comment
        SET body = replace(
            replace(
                replace(
                    replace(
                        replace(body, '&quot;', '"'),
                        '&#x27;', ''''
                    ),
                    '&gt;', '>'
                ),
                '&lt;', '<'
            ),
            '&amp;', '&'
        )
        WHERE body LIKE '%&%';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE comment
        SET body = replace(
            replace(
                replace(
                    replace(
                        replace(body, '&', '&amp;'),
                        '<', '&lt;'
                    ),
                    '>', '&gt;'
                ),
                '"', '&quot;'
            ),
            '''', '&#x27;'
        );
        """
    )

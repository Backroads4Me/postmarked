"""Add oauth_account table for OIDC login.

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-08-10
"""

from typing import Union

import fastapi_users_db_sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "o9p0q1r2s3t4"
down_revision: Union[str, None] = "n8o9p0q1r2s3"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_account",
        sa.Column("id", fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column("user_id", fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column("oauth_name", sa.String(length=100), nullable=False),
        # Text: Azure AD / Authentik access tokens often exceed String(1024).
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("account_id", sa.String(length=320), nullable=False),
        sa.Column("account_email", sa.String(length=320), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_account_oauth_name"), "oauth_account", ["oauth_name"], unique=False)
    op.create_index(op.f("ix_oauth_account_account_id"), "oauth_account", ["account_id"], unique=False)
    op.create_index(
        "ix_oauth_account_oauth_name_account_id",
        "oauth_account",
        ["oauth_name", "account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_account_oauth_name_account_id", table_name="oauth_account")
    op.drop_index(op.f("ix_oauth_account_account_id"), table_name="oauth_account")
    op.drop_index(op.f("ix_oauth_account_oauth_name"), table_name="oauth_account")
    op.drop_table("oauth_account")

"""018 — add token_version column to users table.

Revision ID: 018
Revises: 017
Create Date: 2026-04-11

Migration for SEC-1.1 / SEC-4.4: supports server-side JWT revocation by
incrementing token_version on logout and password change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")

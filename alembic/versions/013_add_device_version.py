"""013 — add optimistic-lock version column to devices.

Revision ID: 013
Revises: 012
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("devices", "version")

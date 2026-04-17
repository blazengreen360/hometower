"""014 — add optimistic-lock version column to diagram_layouts.

Revision ID: 014
Revises: 013
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "diagram_layouts",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("diagram_layouts", "version")

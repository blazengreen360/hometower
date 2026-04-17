"""006 — add unique unordered-pair index for connections.

Revision ID: 006
Revises: 005
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `ck_connections_no_self_loop` already exists from migration 004.
    op.create_index(
        "ix_connections_unique_pair",
        "connections",
        [
            sa.text("LEAST(source_id, target_id)"),
            sa.text("GREATEST(source_id, target_id)"),
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_connections_unique_pair", table_name="connections")

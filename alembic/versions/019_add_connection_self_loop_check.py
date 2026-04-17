"""019 — add explicit self-loop check constraint for connections.

Revision ID: 019
Revises: 018
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_connection_no_self_loop",
        "connections",
        "source_id <> target_id",
    )


def downgrade() -> None:
    op.drop_constraint("ck_connection_no_self_loop", "connections", type_="check")

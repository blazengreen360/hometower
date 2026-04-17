"""016 — enforce unique location names per parent.

Revision ID: 016
Revises: 015
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = "uq_location_parent_name"
_SENTINEL_UUID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.create_index(
            _INDEX_NAME,
            "locations",
            [
                sa.text(
                    f"COALESCE(parent_id, '{_SENTINEL_UUID}'::uuid)"
                ),
                "name",
            ],
            unique=True,
        )
        return

    if dialect == "sqlite":
        op.create_index(
            _INDEX_NAME,
            "locations",
            [sa.text(f"ifnull(parent_id, '{_SENTINEL_UUID}')"), "name"],
            unique=True,
        )
        return

    op.create_index(_INDEX_NAME, "locations", ["parent_id", "name"], unique=True)


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="locations")

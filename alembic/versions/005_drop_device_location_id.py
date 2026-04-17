"""005 — drop location_id column from devices table.

CRITICAL-002: location_id referenced a non-existent locations table.
The Location entity has not been implemented; remove the dangling column.

Revision ID: 005
Revises: 004
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("devices", "location_id")


def downgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("location_id", PG_UUID(as_uuid=True), nullable=True),
    )

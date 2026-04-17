"""008 — add location_id FK to devices table.

Adds a nullable foreign key from devices.location_id → locations.id.
ON DELETE RESTRICT provides defense-in-depth; the service layer enforces
deletion rules and returns user-friendly 400 errors before the DB constraint fires.

Revision ID: 008
Revises: 007
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("location_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_devices_location_id",
        "devices",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_devices_location_id", "devices", type_="foreignkey")
    op.drop_column("devices", "location_id")

"""011 — add status column to devices table (HT-039).

Adds a VARCHAR status column with server_default='Active' so all existing
rows automatically receive the Active status without needing a data migration.

Revision ID: 011
Revises: 010
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("status", sa.String(), server_default="Active", nullable=False),
    )
    op.create_check_constraint(
        "ck_devices_status_valid",
        "devices",
        "status IN ('Active', 'Offline', 'Maintenance', 'Planned', 'Decommissioned')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_devices_status_valid", "devices", type_="check")
    op.drop_column("devices", "status")

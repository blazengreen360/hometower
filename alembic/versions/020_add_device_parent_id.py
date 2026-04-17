"""020 — add parent_id self-referential FK to devices (HT-021 containers).

Adds a nullable self-referential foreign key from devices.parent_id → devices.id
so any device can act as a container for other devices. ON DELETE RESTRICT
provides defense-in-depth; the service layer enforces the "cannot delete with
children" rule and returns a user-friendly 400 before the DB constraint fires.

A CHECK constraint guards against direct self-loops at the DB level (mirrors
ck_connection_no_self_loop from migration 019). Indirect cycle detection
is handled in src/domain/devices.py::detect_parent_cycle.

An index on parent_id supports the get_children, count_children, and
get_parent_map queries used by the service layer on every re-parent.

Revision ID: 020
Revises: 019
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("parent_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_devices_parent_id",
        "devices",
        "devices",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_devices_parent_id", "devices", ["parent_id"])
    op.create_check_constraint(
        "ck_device_no_self_parent",
        "devices",
        "parent_id IS NULL OR parent_id <> id",
    )


def downgrade() -> None:
    op.drop_constraint("ck_device_no_self_parent", "devices", type_="check")
    op.drop_index("ix_devices_parent_id", table_name="devices")
    op.drop_constraint("fk_devices_parent_id", "devices", type_="foreignkey")
    op.drop_column("devices", "parent_id")

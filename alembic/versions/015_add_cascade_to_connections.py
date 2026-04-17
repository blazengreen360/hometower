"""015 — add ON DELETE CASCADE to connections.device foreign keys.

Revision ID: 015
Revises: 014
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_existing_device_fks() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys("connections"):
        columns = fk.get("constrained_columns", [])
        if fk.get("referred_table") == "devices" and columns in (["source_id"], ["target_id"]):
            fk_name = fk.get("name")
            if fk_name:
                op.drop_constraint(fk_name, "connections", type_="foreignkey")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite test DB is created from SQLModel metadata; skip DDL rewrite here.
        return

    _drop_existing_device_fks()
    op.create_foreign_key(
        "fk_connections_source_id_devices",
        "connections",
        "devices",
        ["source_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_connections_target_id_devices",
        "connections",
        "devices",
        ["target_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    op.drop_constraint("fk_connections_source_id_devices", "connections", type_="foreignkey")
    op.drop_constraint("fk_connections_target_id_devices", "connections", type_="foreignkey")
    op.create_foreign_key(
        "fk_connections_source_id_devices",
        "connections",
        "devices",
        ["source_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_connections_target_id_devices",
        "connections",
        "devices",
        ["target_id"],
        ["id"],
    )

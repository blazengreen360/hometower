"""Migration 002 — devices table and device_type enum.

Revision ID: 002
Revises: 001
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL native enum type for device types (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE device_type AS ENUM (
                'Server', 'Switch', 'Router', 'NAS', 'UPS', 'SBC',
                'Workstation', 'VM', 'LXC', 'Docker', 'Application', 'VLAN', 'Subnet'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.create_table(
        "devices",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            PG_ENUM(
                "Server", "Switch", "Router", "NAS", "UPS", "SBC",
                "Workstation", "VM", "LXC", "Docker", "Application", "VLAN", "Subnet",
                name="device_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("mac", sa.String(17), nullable=True),
        sa.Column("os", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # location_id as plain UUID — FK to locations added in a later migration
        sa.Column("location_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_devices_name", "devices", ["name"])
    op.create_index("idx_devices_type", "devices", ["type"])

    # Reuse the trigger function created in migration 001
    op.execute(
        """
        CREATE TRIGGER update_devices_updated_at
        BEFORE UPDATE ON devices
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_devices_updated_at ON devices")
    op.drop_index("idx_devices_type", table_name="devices")
    op.drop_index("idx_devices_name", table_name="devices")
    op.drop_table("devices")
    op.execute("DROP TYPE IF EXISTS device_type")

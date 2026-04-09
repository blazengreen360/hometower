"""004 — create connections table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE connection_type AS ENUM ('Ethernet', 'WiFi', 'Fibre', 'iSCSI', 'NFS', 'VM', 'Other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.create_table(
        "connections",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            PG_ENUM(
                "Ethernet", "WiFi", "Fibre", "iSCSI", "NFS", "VM", "Other",
                name="connection_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["source_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["devices.id"]),
        sa.CheckConstraint("source_id != target_id", name="ck_connections_no_self_loop"),
    )

    op.create_index("ix_connections_source_id", "connections", ["source_id"])
    op.create_index("ix_connections_target_id", "connections", ["target_id"])

    op.execute("""
        CREATE TRIGGER update_connections_updated_at
        BEFORE UPDATE ON connections
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_connections_updated_at ON connections;")
    op.drop_index("ix_connections_target_id", table_name="connections")
    op.drop_index("ix_connections_source_id", table_name="connections")
    op.drop_table("connections")

"""024 - create networks and device_networks tables (HT-022).

Revision ID: 024
Revises: 023
Create Date: 2026-04-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "networks",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("cidr", sa.String(64), nullable=False),
        sa.Column("gateway", sa.String(45), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_networks_vlan_range",
        "networks",
        "vlan_id IS NULL OR (vlan_id BETWEEN 1 AND 4094)",
    )
    op.create_index(
        "ix_networks_name_lower",
        "networks",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.create_index("ix_networks_vlan_id", "networks", ["vlan_id"])

    op.create_table(
        "device_networks",
        sa.Column("device_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("network_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["network_id"], ["networks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id", "network_id"),
    )
    op.create_index("ix_device_networks_network_id", "device_networks", ["network_id"])


def downgrade() -> None:
    op.drop_index("ix_device_networks_network_id", table_name="device_networks")
    op.drop_table("device_networks")

    op.drop_index("ix_networks_vlan_id", table_name="networks")
    op.drop_index("ix_networks_name_lower", table_name="networks")
    op.drop_constraint("ck_networks_vlan_range", "networks", type_="check")
    op.drop_table("networks")

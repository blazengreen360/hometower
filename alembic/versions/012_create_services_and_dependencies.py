"""012 — create services and service_dependencies tables (HT-023).

Creates the services table with per-device case-insensitive name uniqueness
and the service_dependencies join table with CASCADE FKs.

Revision ID: 012
Revises: 011
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("device_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column(
            "protocol",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'other'"),
        ),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column(
            "status",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="ck_services_port_range"),
        sa.CheckConstraint(
            "protocol IN ('http','https','tcp','udp','other')",
            name="ck_services_protocol_valid",
        ),
        sa.CheckConstraint(
            "status IN ('running','stopped','unknown')",
            name="ck_services_status_valid",
        ),
    )
    op.create_index(
        "uq_services_device_name",
        "services",
        ["device_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_table(
        "service_dependencies",
        sa.Column("service_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_id", PG_UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "service_id <> depends_on_id",
            name="ck_service_dep_no_self_ref",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_id"], ["services.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("service_id", "depends_on_id"),
    )
    op.create_index(
        "ix_service_dependencies_depends_on",
        "service_dependencies",
        ["depends_on_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_dependencies_depends_on", table_name="service_dependencies")
    op.drop_constraint(
        "ck_service_dep_no_self_ref",
        "service_dependencies",
        type_="check",
    )
    op.drop_table("service_dependencies")
    op.drop_index("uq_services_device_name", table_name="services")
    op.drop_table("services")

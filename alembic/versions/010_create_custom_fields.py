"""010 — create custom_fields table (HT-007).

Creates the custom_fields table with per-device case-insensitive key uniqueness
enforced via a composite index on (device_id, LOWER(key)).

Revision ID: 010
Revises: 009
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_fields",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("device_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column(
            "value",
            sa.String(1024),
            nullable=False,
            server_default=sa.text("''"),
        ),
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
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_custom_fields_device_key_lower",
        "custom_fields",
        ["device_id", sa.text("LOWER(key)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_custom_fields_device_key_lower", table_name="custom_fields")
    op.drop_table("custom_fields")

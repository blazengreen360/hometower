"""027 - create device attachments table (HT-042).

Revision ID: 027
Revises: 026
Create Date: 2026-04-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_attachments_device_id",
        "device_attachments",
        ["device_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_device_attachments_size_non_negative",
        "device_attachments",
        "size_bytes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_device_attachments_size_non_negative",
        "device_attachments",
        type_="check",
    )
    op.drop_index("ix_device_attachments_device_id", table_name="device_attachments")
    op.drop_table("device_attachments")
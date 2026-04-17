"""009 — create tags and device_tags tables (HT-006).

Creates the tags table with a case-insensitive unique index on name,
and the device_tags join table with composite PK and CASCADE on both FKs.

Revision ID: 009
Revises: 008
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_tags_name_lower",
        "tags",
        [sa.text("LOWER(name)")],
        unique=True,
    )
    op.create_table(
        "device_tags",
        sa.Column("device_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", PG_UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("device_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("device_tags")
    op.drop_index("ix_tags_name_lower", table_name="tags")
    op.drop_table("tags")

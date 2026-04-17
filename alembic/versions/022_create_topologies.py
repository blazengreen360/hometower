"""022 — create topologies table (HT-047).

Revision ID: 022
Revises: 021
Create Date: 2026-04-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "topologies",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("workspace_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("tags", sa.JSON(), server_default="[]", nullable=False),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
            name="fk_topologies_workspace_id",
        ),
        sa.UniqueConstraint(
            "workspace_id", "name", name="uq_topology_workspace_name"
        ),
    )
    op.create_index(
        "ix_topologies_workspace_id", "topologies", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_topologies_workspace_id", table_name="topologies")
    op.drop_table("topologies")

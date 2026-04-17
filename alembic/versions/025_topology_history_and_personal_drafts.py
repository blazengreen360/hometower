"""025 - topology history foundation and personal drafts (HT-072).

Revision ID: 025
Revises: 024
Create Date: 2026-04-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "topologies",
        sa.Column("current_diagram_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_topologies_current_diagram_id",
        "topologies",
        "diagram_layouts",
        ["current_diagram_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_topologies_current_diagram_id",
        "topologies",
        ["current_diagram_id"],
    )

    op.create_table(
        "topology_history_entries",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("topology_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("diagram_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_name", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False, server_default=sa.text("'save_version'")),
        sa.Column("restored_from_history_entry_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["topology_id"], ["topologies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagram_layouts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["restored_from_history_entry_id"],
            ["topology_history_entries.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_topology_history_entries_topology_id",
        "topology_history_entries",
        ["topology_id"],
    )
    op.create_index(
        "ix_topology_history_entries_diagram_id",
        "topology_history_entries",
        ["diagram_id"],
    )
    op.create_index(
        "ix_topology_history_entries_created_at",
        "topology_history_entries",
        ["created_at"],
    )

    op.create_table(
        "topology_personal_drafts",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("topology_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("cytoscape_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
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
        sa.ForeignKeyConstraint(["topology_id"], ["topologies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("topology_id", "user_id", name="uq_topology_personal_drafts_topology_user"),
    )
    op.create_index(
        "ix_topology_personal_drafts_topology_id",
        "topology_personal_drafts",
        ["topology_id"],
    )
    op.create_index(
        "ix_topology_personal_drafts_user_id",
        "topology_personal_drafts",
        ["user_id"],
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            WITH latest AS (
                SELECT DISTINCT ON (topology_id)
                    topology_id,
                    id AS diagram_id
                FROM diagram_layouts
                WHERE topology_id IS NOT NULL
                ORDER BY topology_id, updated_at DESC, created_at DESC, id DESC
            )
            UPDATE topologies AS t
            SET current_diagram_id = latest.diagram_id
            FROM latest
            WHERE t.id = latest.topology_id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO topology_history_entries (
                id,
                topology_id,
                diagram_id,
                snapshot_name,
                action,
                created_at
            )
            SELECT
                gen_random_uuid(),
                d.topology_id,
                d.id,
                d.name,
                'backfill',
                d.created_at
            FROM diagram_layouts AS d
            WHERE d.topology_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_topology_personal_drafts_user_id", table_name="topology_personal_drafts")
    op.drop_index("ix_topology_personal_drafts_topology_id", table_name="topology_personal_drafts")
    op.drop_table("topology_personal_drafts")

    op.drop_index("ix_topology_history_entries_created_at", table_name="topology_history_entries")
    op.drop_index("ix_topology_history_entries_diagram_id", table_name="topology_history_entries")
    op.drop_index("ix_topology_history_entries_topology_id", table_name="topology_history_entries")
    op.drop_table("topology_history_entries")

    op.drop_index("ix_topologies_current_diagram_id", table_name="topologies")
    op.drop_constraint("fk_topologies_current_diagram_id", "topologies", type_="foreignkey")
    op.drop_column("topologies", "current_diagram_id")

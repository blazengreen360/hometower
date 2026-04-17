"""023 — add topology_id FK to diagram_layouts + backfill (HT-047).

Three-phase migration:
1. Add nullable topology_id column with FK to topologies.
2. Backfill: create Default Workspace + Default Topology for the first admin,
   then assign all orphan diagram layouts.
3. Create index on topology_id.

Revision ID: 023
Revises: 022
Create Date: 2026-04-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 1: add nullable column
    op.add_column(
        "diagram_layouts",
        sa.Column("topology_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_diagram_layouts_topology_id",
        "diagram_layouts",
        "topologies",
        ["topology_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Phase 2: backfill
    conn = op.get_bind()

    admin = conn.execute(
        sa.text(
            "SELECT id FROM users WHERE role = 'Admin' "
            "ORDER BY created_at LIMIT 1"
        )
    ).fetchone()

    if admin is not None:
        admin_id = admin[0]
        ws_id = conn.execute(
            sa.text(
                "INSERT INTO workspaces (id, name, owner_id) "
                "VALUES (gen_random_uuid(), 'Default Workspace', :owner_id) "
                "RETURNING id"
            ),
            {"owner_id": admin_id},
        ).fetchone()[0]

        topo_id = conn.execute(
            sa.text(
                "INSERT INTO topologies (id, name, workspace_id) "
                "VALUES (gen_random_uuid(), 'Default Topology', :ws_id) "
                "RETURNING id"
            ),
            {"ws_id": ws_id},
        ).fetchone()[0]

        conn.execute(
            sa.text(
                "UPDATE diagram_layouts SET topology_id = :topo_id "
                "WHERE topology_id IS NULL"
            ),
            {"topo_id": topo_id},
        )

    # Phase 3: index
    op.create_index(
        "ix_diagram_layouts_topology_id",
        "diagram_layouts",
        ["topology_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_diagram_layouts_topology_id", table_name="diagram_layouts"
    )
    op.drop_constraint(
        "fk_diagram_layouts_topology_id",
        "diagram_layouts",
        type_="foreignkey",
    )
    op.drop_column("diagram_layouts", "topology_id")

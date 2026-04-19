"""028 - persist device ownership with provable backfill.

Revision ID: 028
Revises: 027
Create Date: 2026-04-19
"""
from collections import defaultdict
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _extract_device_ids(cytoscape_json: object) -> set[uuid.UUID]:
    if not isinstance(cytoscape_json, dict):
        return set()
    elements = cytoscape_json.get("elements")
    nodes = elements.get("nodes") if isinstance(elements, dict) else elements
    if not isinstance(nodes, list):
        return set()
    device_ids: set[uuid.UUID] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        group = node.get("group")
        if group is not None and group != "nodes":
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        candidate = data.get("device_id", data.get("id"))
        if candidate is None:
            continue
        try:
            device_ids.add(uuid.UUID(str(candidate)))
        except ValueError:
            continue
    return device_ids


def _backfill_device_owners() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT w.owner_id, d.cytoscape_json
            FROM topologies AS t
            JOIN workspaces AS w ON w.id = t.workspace_id
            JOIN diagram_layouts AS d ON d.id = t.current_diagram_id
            WHERE t.current_diagram_id IS NOT NULL
            """
        )
    ).mappings()
    owner_candidates: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for row in rows:
        owner_id = row["owner_id"]
        if owner_id is None:
            continue
        # Only use current topology ownership because it is the only
        # persisted, provable owner signal available in the pre-migration data.
        for device_id in _extract_device_ids(row["cytoscape_json"]):
            owner_candidates[device_id].add(owner_id)
    owner_updates = [
        {"device_id": device_id, "owner_id": next(iter(owner_ids))}
        for device_id, owner_ids in owner_candidates.items()
        if len(owner_ids) == 1
    ]
    if owner_updates:
        # Batch only provable single-owner assignments; ambiguous or unplaced devices stay NULL.
        conn.execute(
            sa.text(
                """
                UPDATE devices
                SET owner_id = :owner_id
                WHERE id = :device_id AND owner_id IS NULL
                """
            ),
            owner_updates,
        )


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("owner_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_devices_owner_id",
        "devices",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _backfill_device_owners()
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_devices_owner_id",
            "devices",
            ["owner_id"],
            unique=False,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_devices_owner_id",
            table_name="devices",
            postgresql_concurrently=True,
        )
    op.drop_constraint("fk_devices_owner_id", "devices", type_="foreignkey")
    op.drop_column("devices", "owner_id")

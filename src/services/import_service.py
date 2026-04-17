"""Import service — TRUNCATE-then-INSERT full-snapshot restore (HT-013)."""
from sqlalchemy import text
from sqlmodel import Session

from src.services.import_validation import (
    validate_device_network_refs,
    validate_device_network_subnets,
    validate_device_location_refs,
    validate_device_parent_refs,
    validate_network_rows,
)
from src.models.export_schema import ExportSchema
from src.services.import_service_rows import insert_snapshot_rows
from src.utils.logger import logger


def _is_postgres(session: Session) -> bool:
    try:
        bind = session.get_bind()
        return bind.dialect.name == "postgresql"
    except (AttributeError, TypeError):
        return False


def _clear_all_tables(session: Session) -> None:
    """Remove all rows from every table in reverse-dependency order."""
    # NOTE (BUG-001 mitigation): historically we used `TRUNCATE ... CASCADE`
    # on PostgreSQL which takes an ACCESS EXCLUSIVE lock on every table and
    # can cause broad lock contention and blocking in busy systems
    # (see doc/bugs/bug-report-14-04-26.1.md). To reduce lock risk while
    # keeping the import atomic and rollback-safe we perform ordered
    # `DELETE FROM <table>` statements inside the caller's transaction.
    # DELETE uses row-level MVCC and avoids the global table-level exclusive
    # locks that TRUNCATE requires. If the dataset is very large this will
    # be slower and generate WAL bloat; for high-volume imports consider a
    # schema-swap approach implemented outside the live-path import.
    # The deletion order below is reverse-dependency so FK constraints are
    # honored.
    tables = [
        "service_dependencies",
        "services",
        "custom_fields",
        "device_attachments",
        "device_networks",
        "device_tags",
        "connections",
        "topology_personal_drafts",
        "topology_history_entries",
        "diagram_layouts",
        "devices",
        "networks",
        "topologies",
        "locations",
        "tags",
        "power_settings",
        "workspaces",
        "users",
    ]
    for table in tables:
        # Use plain DELETE so this code path is safe for Postgres and SQLite.
        session.exec(text(f"DELETE FROM {table}"))  # type: ignore[call-overload]


def import_full_snapshot(
    session: Session, payload: ExportSchema
) -> dict[str, int]:
    """Destructively replace all data with the contents of *payload*."""
    logger.info("import_full_snapshot: starting replace — version={v}", v=payload.version)

    validate_device_location_refs(payload)
    validate_device_parent_refs(payload)
    validate_network_rows(payload)
    validate_device_network_refs(payload)
    validate_device_network_subnets(payload)
    _clear_all_tables(session)
    # Remove stale identity-map objects so re-inserting same primary keys is conflict-free.
    session.expunge_all()
    insert_snapshot_rows(session, payload)

    counts = {
        "users": len(payload.users),
        "workspaces": len(payload.workspaces),
        "topologies": len(payload.topologies),
        "locations": len(payload.locations),
        "tags": len(payload.tags),
        "networks": len(payload.networks),
        "devices": len(payload.devices),
        "device_networks": len(payload.device_networks),
        "services": len(payload.services),
        "service_dependencies": len(payload.service_dependencies),
        "connections": len(payload.connections),
        "device_tags": len(payload.device_tags),
        "custom_fields": len(payload.custom_fields),
        "diagram_layouts": len(payload.diagram_layouts),
    }
    logger.info("import_full_snapshot: complete — {counts}", counts=counts)
    return counts

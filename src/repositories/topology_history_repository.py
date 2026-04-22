"""Topology history repository for immutable topology checkpoints."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.topology_history_entry import TopologyHistoryEntry


def create(session: Session, entry: TopologyHistoryEntry) -> TopologyHistoryEntry:
    """Persist a new history entry and return the refreshed instance."""
    session.add(entry)
    session.flush()
    session.refresh(entry)
    return entry


def get_by_id(session: Session, history_entry_id: uuid.UUID) -> TopologyHistoryEntry | None:
    """Return a history entry by primary key."""
    return session.get(TopologyHistoryEntry, history_entry_id)


def get_by_topology_and_id(
    session: Session,
    topology_id: uuid.UUID,
    history_entry_id: uuid.UUID,
) -> TopologyHistoryEntry | None:
    """Return a history entry when it belongs to the given topology."""
    statement = select(TopologyHistoryEntry).where(
        TopologyHistoryEntry.topology_id == topology_id,
        TopologyHistoryEntry.id == history_entry_id,
    )
    return session.exec(statement).first()


def list_by_topology(
    session: Session,
    topology_id: uuid.UUID,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[TopologyHistoryEntry], int]:
    """Return paginated history entries for a topology and the total count."""
    base = select(TopologyHistoryEntry).where(TopologyHistoryEntry.topology_id == topology_id)
    total = int(session.exec(select(func.count()).select_from(base.subquery())).one())
    offset = (page - 1) * limit
    statement = (
        base.order_by(col(TopologyHistoryEntry.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def get_immutable_diagram_ids(
    session: Session,
    diagram_ids: set[uuid.UUID],
) -> set[uuid.UUID]:
    """Return diagram ids that are referenced by immutable history entries."""
    if not diagram_ids:
        return set()
    statement = select(TopologyHistoryEntry.diagram_id).where(
        col(TopologyHistoryEntry.diagram_id).in_(diagram_ids)
    )
    return set(session.exec(statement).all())

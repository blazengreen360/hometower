"""Topology repository — sole layer that holds a SQLModel Session for topology operations."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.topology import Topology


def create(session: Session, topology: Topology) -> Topology:
    """Persist a new topology and return the refreshed instance."""
    session.add(topology)
    session.flush()
    session.refresh(topology)
    return topology


def get_by_id(session: Session, topology_id: uuid.UUID) -> Topology | None:
    """Return the topology with the given primary key, or None."""
    return session.get(Topology, topology_id)


def get_by_workspace(
    session: Session, workspace_id: uuid.UUID, page: int = 1, limit: int = 50
) -> tuple[list[Topology], int]:
    """Return paginated topologies for a workspace and the total count."""
    base = select(Topology).where(Topology.workspace_id == workspace_id)
    total = int(
        session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()
    )
    offset = (page - 1) * limit
    statement = (
        base.order_by(col(Topology.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def get_by_workspace_and_name(
    session: Session, workspace_id: uuid.UUID, name: str
) -> Topology | None:
    """Return a topology by workspace and name, or None."""
    statement = select(Topology).where(
        Topology.workspace_id == workspace_id, Topology.name == name
    )
    return session.exec(statement).first()


def update(session: Session, topology: Topology) -> Topology:
    """Persist changes to an already-fetched topology and return it."""
    session.add(topology)
    session.flush()
    session.refresh(topology)
    return topology


def delete(session: Session, topology: Topology) -> None:
    """Hard-delete a topology record. CASCADE handles children."""
    session.delete(topology)
    session.flush()


def count_views(session: Session, topology_id: uuid.UUID) -> int:
    """Return the number of diagram layouts (views) in a topology."""
    from src.models.diagram import DiagramLayout

    statement = (
        select(func.count())
        .select_from(DiagramLayout)
        .where(DiagramLayout.topology_id == topology_id)
    )
    return int(session.exec(statement).one())


def count_views_batch(
    session: Session, topology_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Return view counts for multiple topologies in a single query."""
    if not topology_ids:
        return {}
    from src.models.diagram import DiagramLayout

    statement = (
        select(DiagramLayout.topology_id, func.count())
        .where(col(DiagramLayout.topology_id).in_(topology_ids))
        .group_by(col(DiagramLayout.topology_id))
    )
    rows = session.exec(statement).all()
    return {uuid.UUID(str(tid)): int(cnt) for tid, cnt in rows}


def get_all_for_export(session: Session) -> list[Topology]:
    """Return all topologies ordered by created_at ASC (no pagination)."""
    statement = select(Topology).order_by(col(Topology.created_at))
    return list(session.exec(statement).all())

"""DiagramLayout repository — sole layer that holds a SQLModel Session for diagram operations."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.workspace import Workspace


def create(session: Session, layout: DiagramLayout) -> DiagramLayout:
    """Persist a new diagram layout and return the refreshed instance."""
    session.add(layout)
    session.flush()
    session.refresh(layout)
    return layout


def update(session: Session, layout: DiagramLayout) -> DiagramLayout:
    """Persist changes to an already-fetched layout and return it."""
    session.add(layout)
    session.flush()
    session.refresh(layout)
    return layout


def get_by_id(session: Session, layout_id: uuid.UUID) -> DiagramLayout | None:
    """Return the layout with the given primary key, or None."""
    return session.get(DiagramLayout, layout_id)


def get_by_id_for_owner(
    session: Session,
    layout_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> DiagramLayout | None:
    """Return a layout by ID only when it belongs to the provided owner."""
    statement = (
        select(DiagramLayout)
        .join(Topology, col(DiagramLayout.topology_id) == col(Topology.id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
        .where(col(DiagramLayout.id) == layout_id)
        .where(col(Workspace.owner_id) == owner_id)
    )
    return session.exec(statement).first()


def get_by_id_for_update(session: Session, layout_id: uuid.UUID) -> DiagramLayout | None:
    """Return the layout by ID while acquiring a row lock for this transaction."""
    statement = (
        select(DiagramLayout)
        .where(DiagramLayout.id == layout_id)
        .with_for_update()
    )
    return session.exec(statement).first()


def get_all(session: Session, page: int = 1, limit: int = 50) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts and the total count."""
    total = int(session.exec(select(func.count()).select_from(DiagramLayout)).one())
    offset = (page - 1) * limit
    statement = (
        select(DiagramLayout)
        .order_by(col(DiagramLayout.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def get_all_for_owner(
    session: Session,
    owner_id: uuid.UUID,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[DiagramLayout], int]:
    """Return paginated layouts visible to the owner."""
    base = (
        select(DiagramLayout)
        .join(Topology, col(DiagramLayout.topology_id) == col(Topology.id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
        .where(col(Workspace.owner_id) == owner_id)
    )
    total = int(session.exec(select(func.count()).select_from(base.subquery())).one())
    offset = (page - 1) * limit
    statement = (
        base.order_by(col(DiagramLayout.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def get_all_for_export(session: Session) -> list[DiagramLayout]:
    """Return all diagram layouts ordered by created_at ASC (no pagination)."""
    statement = select(DiagramLayout).order_by(col(DiagramLayout.created_at))
    return list(session.exec(statement).all())


def get_by_topology(
    session: Session, topology_id: uuid.UUID, page: int = 1, limit: int = 50
) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts for a topology and the total count."""
    base = select(DiagramLayout).where(DiagramLayout.topology_id == topology_id)
    total = int(
        session.exec(select(func.count()).select_from(base.subquery())).one()
    )
    offset = (page - 1) * limit
    statement = (
        base.order_by(col(DiagramLayout.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def get_by_topology_for_owner(
    session: Session,
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts for a topology owned by the caller."""
    base = (
        select(DiagramLayout)
        .join(Topology, col(DiagramLayout.topology_id) == col(Topology.id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
        .where(col(DiagramLayout.topology_id) == topology_id)
        .where(col(Workspace.owner_id) == owner_id)
    )
    total = int(session.exec(select(func.count()).select_from(base.subquery())).one())
    offset = (page - 1) * limit
    statement = (
        base.order_by(col(DiagramLayout.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def count_by_topology(session: Session, topology_id: uuid.UUID) -> int:
    """Return the number of diagram layouts in a topology."""
    statement = (
        select(func.count())
        .select_from(DiagramLayout)
        .where(DiagramLayout.topology_id == topology_id)
    )
    return int(session.exec(statement).one())


def delete(session: Session, layout: DiagramLayout) -> None:
    """Hard-delete a diagram layout record."""
    session.delete(layout)
    session.flush()


def get_all_layouts(session: Session) -> list[DiagramLayout]:
    """Return every diagram layout (no pagination). Used for device placement scans."""
    statement = select(DiagramLayout).order_by(col(DiagramLayout.created_at))
    return list(session.exec(statement).all())

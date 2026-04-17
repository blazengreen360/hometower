"""Workspace repository — sole layer that holds a SQLModel Session for workspace operations."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.workspace import Workspace


def create(session: Session, workspace: Workspace) -> Workspace:
    """Persist a new workspace and return the refreshed instance."""
    session.add(workspace)
    session.flush()
    session.refresh(workspace)
    return workspace


def get_by_id(session: Session, workspace_id: uuid.UUID) -> Workspace | None:
    """Return the workspace with the given primary key, or None."""
    return session.get(Workspace, workspace_id)


def get_by_owner(
    session: Session, owner_id: uuid.UUID, page: int = 1, limit: int = 50,
    search: str | None = None,
) -> tuple[list[Workspace], int]:
    """Return paginated workspaces for an owner and the total count."""
    base = select(Workspace).where(Workspace.owner_id == owner_id)
    if search:
        base = base.where(col(Workspace.name).contains(search))
    total = int(
        session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()
    )
    offset = (page - 1) * limit
    statement = (
        base.order_by(col(Workspace.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def get_by_owner_and_name(
    session: Session, owner_id: uuid.UUID, name: str
) -> Workspace | None:
    """Return a workspace by owner and name, or None."""
    statement = select(Workspace).where(
        Workspace.owner_id == owner_id, Workspace.name == name
    )
    return session.exec(statement).first()


def update(session: Session, workspace: Workspace) -> Workspace:
    """Persist changes to an already-fetched workspace and return it."""
    session.add(workspace)
    session.flush()
    session.refresh(workspace)
    return workspace


def delete(session: Session, workspace: Workspace) -> None:
    """Hard-delete a workspace record. CASCADE handles children."""
    session.delete(workspace)
    session.flush()


def count_topologies(session: Session, workspace_id: uuid.UUID) -> int:
    """Return the number of topologies in a workspace."""
    from src.models.topology import Topology

    statement = (
        select(func.count())
        .select_from(Topology)
        .where(Topology.workspace_id == workspace_id)
    )
    return int(session.exec(statement).one())


def count_topologies_batch(
    session: Session, workspace_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Return topology counts for multiple workspaces in a single query."""
    if not workspace_ids:
        return {}
    from src.models.topology import Topology

    statement = (
        select(Topology.workspace_id, func.count())
        .where(col(Topology.workspace_id).in_(workspace_ids))
        .group_by(col(Topology.workspace_id))
    )
    rows = session.exec(statement).all()
    return {uuid.UUID(str(ws_id)): int(cnt) for ws_id, cnt in rows}


def get_all_for_export(session: Session) -> list[Workspace]:
    """Return all workspaces ordered by created_at ASC (no pagination)."""
    statement = select(Workspace).order_by(col(Workspace.created_at))
    return list(session.exec(statement).all())

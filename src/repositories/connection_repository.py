"""Connection repository — sole layer that holds a SQLModel Session for Connection operations."""
import uuid

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from src.models.connection import Connection
from src.models.device import Device
from src.repositories.device_repository_support import apply_owner_scope
from src.repositories.device_repository_support import get_workspace_device_ids


def create(session: Session, connection: Connection) -> Connection:
    """Persist a new connection and return the refreshed instance."""
    session.add(connection)
    session.flush()
    session.refresh(connection)
    return connection


def _get_scoped_device_ids(
    session: Session,
    owner_id: uuid.UUID | None,
) -> set[uuid.UUID] | None:
    if owner_id is None:
        return None

    device_ids = get_workspace_device_ids(session, None, owner_id)
    if device_ids is not None:
        return device_ids

    statement = apply_owner_scope(select(Device.id), session, col, owner_id)
    return set(session.exec(statement).all())


def _apply_connection_owner_scope(statement, device_ids: set[uuid.UUID] | None):
    if device_ids is None:
        return statement
    return statement.where(
        col(Connection.source_id).in_(device_ids),
        col(Connection.target_id).in_(device_ids),
    )


def get_by_id(
    session: Session,
    connection_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
) -> Connection | None:
    """Return the connection with the given primary key, or None."""
    device_ids = _get_scoped_device_ids(session, owner_id)
    statement = _apply_connection_owner_scope(
        select(Connection).where(col(Connection.id) == connection_id),
        device_ids,
    )
    return session.exec(statement).first()


def get_all(
    session: Session,
    page: int = 1,
    limit: int = 50,
    source_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[Connection], int]:
    """Return a filtered, paginated list of connections and total count."""
    device_ids = _get_scoped_device_ids(session, owner_id)
    stmt = _apply_connection_owner_scope(select(Connection), device_ids)
    count_stmt = _apply_connection_owner_scope(
        select(func.count()).select_from(Connection),
        device_ids,
    )

    if source_id is not None:
        stmt = stmt.where(col(Connection.source_id) == source_id)
        count_stmt = count_stmt.where(col(Connection.source_id) == source_id)
    if target_id is not None:
        stmt = stmt.where(col(Connection.target_id) == target_id)
        count_stmt = count_stmt.where(col(Connection.target_id) == target_id)

    total = int(session.exec(count_stmt).one())
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit).order_by(col(Connection.created_at))
    items = list(session.exec(stmt).all())
    return items, total


def get_all_for_export(session: Session) -> list[Connection]:
    """Return all connections ordered by created_at ASC (no pagination)."""
    stmt = select(Connection).order_by(col(Connection.created_at))
    return list(session.exec(stmt).all())


def update(session: Session, connection: Connection) -> Connection:
    """Persist changes to an already-fetched connection and return it."""
    session.add(connection)
    session.flush()
    session.refresh(connection)
    return connection


def delete(session: Session, connection: Connection) -> None:
    """Hard-delete a connection record."""
    session.delete(connection)
    session.flush()


def count_by_device(session: Session, device_id: uuid.UUID) -> int:
    """Count connections where device is source OR target."""
    stmt = select(func.count()).select_from(Connection).where(
        or_(col(Connection.source_id) == device_id, col(Connection.target_id) == device_id)
    )
    return int(session.exec(stmt).one())


def get_by_device(
    session: Session,
    device_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
) -> list[Connection]:
    """Return all connections where device_id is source OR target, ordered by created_at ASC."""
    device_ids = _get_scoped_device_ids(session, owner_id)
    stmt = _apply_connection_owner_scope(
        select(Connection)
        .where(
            or_(
                col(Connection.source_id) == device_id,
                col(Connection.target_id) == device_id,
            )
        )
        .order_by(col(Connection.created_at)),
        device_ids,
    )
    return list(session.exec(stmt).all())


def exists_between(session: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> bool:
    """Return True if a connection already exists between the two devices in either direction."""
    stmt = select(func.count()).select_from(Connection).where(
        or_(
            (col(Connection.source_id) == source_id) & (col(Connection.target_id) == target_id),
            (col(Connection.source_id) == target_id) & (col(Connection.target_id) == source_id),
        )
    )
    return int(session.exec(stmt).one()) > 0


def delete_by_device(session: Session, device_id: uuid.UUID) -> int:
    """Delete all connections where device_id is source OR target. Return count deleted."""
    connections = get_by_device(session, device_id)
    for conn in connections:
        session.delete(conn)
    if connections:
        session.flush()
    return len(connections)

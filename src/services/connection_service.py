"""Connection service — orchestrates domain logic and connection repository."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import connections as connection_domain
from src.models.connection import Connection, ConnectionCreate, ConnectionUpdate
from src.repositories import connection_repository, device_repository
from src.utils.logger import logger


def _raise_connection_conflict(exc: IntegrityError, session: Session) -> None:
    """Rollback failed writes and map update conflicts to HTTP 409."""
    session.rollback()
    raise HTTPException(status_code=409, detail="Connection update conflict") from exc


def _validate_updated_connection_devices(
    update_data: dict[str, object],
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    if (
        "source_id" in update_data
        and device_repository.get_by_id(session, source_id, owner_id=owner_id) is None
    ):
        raise HTTPException(status_code=400, detail="Source device not found")
    if (
        "target_id" in update_data
        and device_repository.get_by_id(session, target_id, owner_id=owner_id) is None
    ):
        raise HTTPException(status_code=400, detail="Target device not found")


def _validate_updated_connection_pair(
    conn: Connection,
    update_data: dict[str, object],
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    session: Session,
) -> None:
    if "source_id" not in update_data and "target_id" not in update_data:
        return

    try:
        connection_domain.validate_no_self_loop(source_id, target_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    current_pair = frozenset((conn.source_id, conn.target_id))
    requested_pair = frozenset((source_id, target_id))
    if requested_pair != current_pair and connection_repository.exists_between(
        session,
        source_id,
        target_id,
    ):
        raise HTTPException(
            status_code=409,
            detail="Connection already exists between these devices",
        )


def create(
    data: ConnectionCreate,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> Connection:
    """Validate and persist a new connection."""
    try:
        connection_domain.validate_no_self_loop(data.source_id, data.target_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if device_repository.get_by_id(session, data.source_id, owner_id=owner_id) is None:
        raise HTTPException(status_code=400, detail="Source device not found")
    if device_repository.get_by_id(session, data.target_id, owner_id=owner_id) is None:
        raise HTTPException(status_code=400, detail="Target device not found")
    if connection_repository.exists_between(session, data.source_id, data.target_id):
        raise HTTPException(
            status_code=409,
            detail="Connection already exists between these devices",
        )

    conn = Connection(
        source_id=data.source_id,
        target_id=data.target_id,
        type=data.type,
        label=data.label,
    )
    try:
        result = connection_repository.create(session, conn)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "ix_connections_unique_pair" in str(exc.orig):
            raise HTTPException(
                status_code=409,
                detail="Connection already exists between these devices",
            ) from exc
        logger.exception("Unmapped IntegrityError in connection create")
        raise HTTPException(status_code=500, detail="Internal database error") from exc
    logger.info(
        "Connection created: id={} source={} target={}",
        result.id, result.source_id, result.target_id,
    )
    return result


def get_by_id(
    connection_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> Connection:
    """Return the connection or raise HTTP 404."""
    conn = connection_repository.get_by_id(session, connection_id, owner_id=owner_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


def get_all(
    session: Session,
    page: int,
    limit: int,
    source_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[Connection], int]:
    """Return a paginated, filtered list of connections and total count."""
    return connection_repository.get_all(
        session,
        page,
        limit,
        source_id,
        target_id,
        owner_id=owner_id,
    )


def get_connections_for_device(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[Connection]:
    """Return all connections where the given device is source or target."""
    if device_repository.get_by_id(session, device_id, owner_id=owner_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return connection_repository.get_by_device(session, device_id, owner_id=owner_id)


def update(
    connection_id: uuid.UUID,
    data: ConnectionUpdate,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> Connection:
    """Partially update a connection; raise HTTP 404 if not found."""
    conn = get_by_id(connection_id, session, owner_id=owner_id)

    update_data = data.model_dump(exclude_unset=True)
    source_id = update_data.get("source_id", conn.source_id)
    target_id = update_data.get("target_id", conn.target_id)

    _validate_updated_connection_devices(
        update_data,
        source_id,
        target_id,
        session,
        owner_id=owner_id,
    )
    _validate_updated_connection_pair(conn, update_data, source_id, target_id, session)

    for field, value in update_data.items():
        setattr(conn, field, value)
    conn.updated_at = datetime.now(timezone.utc)
    try:
        result = connection_repository.update(session, conn)
        session.commit()
    except IntegrityError as exc:
        _raise_connection_conflict(exc, session)
    logger.info("Connection updated: id={}", result.id)
    return result


def delete(
    connection_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    """Delete a connection; raise HTTP 404 if not found."""
    conn = connection_repository.get_by_id(session, connection_id, owner_id=owner_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    connection_repository.delete(session, conn)
    session.commit()
    logger.info("Connection deleted: id={}", connection_id)

"""Device repository — sole layer that holds a SQLModel Session for Device operations."""
import uuid
from typing import Optional

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from src.models.device import Device
from src.models.location import Location
from src.repositories.device_repository_support import apply_device_scope
from src.repositories.device_repository_support import apply_owner_scope
from src.repositories.device_repository_support import get_order_expression
from src.repositories.device_repository_support import get_workspace_device_ids
from src.repositories.device_repository_search_support import apply_search_filters
from src.repositories.device_repository_search_support import build_search_statement


def create(session: Session, device: Device) -> Device:
    session.add(device)
    session.flush()
    session.refresh(device)
    return device


def get_by_id(
    session: Session,
    device_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
    enforce_owner_scope: bool = True,
) -> Device | None:
    scoped_owner_id = owner_id if enforce_owner_scope else None
    device_ids = get_workspace_device_ids(session, None, scoped_owner_id)
    statement = apply_device_scope(
        select(Device).where(col(Device.id) == device_id),
        session,
        col,
        device_ids,
        scoped_owner_id,
    )
    return session.exec(statement).first()

def get_all(
    session: Session,
    page: int = 1,
    limit: int = 50,
    sort: Optional[str] = None,
    workspace_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[Device], int]:
    device_ids = get_workspace_device_ids(session, workspace_id, owner_id)
    base = apply_device_scope(select(Device), session, col, device_ids, owner_id)
    total = int(
        session.execute(
            sa_select(func.count()).select_from(base.subquery())  # type: ignore[arg-type]
        ).scalar_one()
    )
    offset = (page - 1) * limit
    order_expr = get_order_expression(sort, col)
    statement = base.order_by(order_expr).offset(offset).limit(limit)
    items = list(session.exec(statement).all())
    return items, total

def get_all_for_export(
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[Device]:
    statement = select(Device).order_by(col(Device.created_at))
    device_ids = get_workspace_device_ids(session, None, owner_id)
    statement = apply_owner_scope(statement, session, col, owner_id)
    if device_ids is not None:
        statement = statement.where(col(Device.id).in_(device_ids))
    return list(session.exec(statement).all())

def update(session: Session, device: Device) -> Device:
    session.add(device)
    session.flush()
    session.refresh(device)
    return device

def delete(session: Session, device: Device) -> None:
    session.delete(device)
    session.flush()

def count(session: Session) -> int:
    result = session.exec(select(func.count()).select_from(Device)).one()
    return int(result)

def get_children(
    session: Session,
    parent_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
) -> list[Device]:
    device_ids = get_workspace_device_ids(session, None, owner_id)
    statement = (
        select(Device)
        .where(col(Device.parent_id) == parent_id)
        .order_by(col(Device.name))
    )
    statement = apply_owner_scope(statement, session, col, owner_id)
    if device_ids is not None:
        statement = statement.where(col(Device.id).in_(device_ids))
    return list(session.exec(statement).all())


def count_children(
    session: Session,
    parent_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
) -> int:
    device_ids = get_workspace_device_ids(session, None, owner_id)
    statement = (
        select(func.count())
        .select_from(Device)
        .where(col(Device.parent_id) == parent_id)
    )
    statement = apply_owner_scope(statement, session, col, owner_id)
    if device_ids is not None:
        statement = statement.where(col(Device.id).in_(device_ids))
    result = session.exec(statement).one()
    return int(result)

def get_parent_map(
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, Optional[uuid.UUID]]:
    device_ids = get_workspace_device_ids(session, None, owner_id)
    statement = select(Device.id, Device.parent_id)
    statement = apply_owner_scope(statement, session, col, owner_id)
    if device_ids is not None:
        statement = statement.where(col(Device.id).in_(device_ids))
    rows = session.exec(statement).all()
    return {row[0]: row[1] for row in rows}

def get_all_with_location(
    session: Session, page: int = 1, limit: int = 1000,
    sort: Optional[str] = None,
    workspace_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[tuple[Device, str | None]], int]:
    device_ids = get_workspace_device_ids(session, workspace_id, owner_id)
    offset = (page - 1) * limit
    order_expr = get_order_expression(sort, col)
    base = (
        sa_select(Device, Location.name)  # type: ignore[call-overload]
        .outerjoin(Location, Device.location_id == Location.id)
    )
    stmt = apply_device_scope(base, session, col, device_ids, owner_id)
    total = int(
        session.execute(
            sa_select(func.count()).select_from(stmt.subquery())  # type: ignore[arg-type]
        ).scalar_one()
    )
    rows = list(session.execute(stmt.order_by(order_expr).offset(offset).limit(limit)).all())
    return [(row[0], row[1]) for row in rows], total

def get_all_names(
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[str]:
    statement = select(Device.name).order_by(col(Device.created_at))
    device_ids = get_workspace_device_ids(session, None, owner_id)
    statement = apply_owner_scope(statement, session, col, owner_id)
    if device_ids is not None:
        statement = statement.where(col(Device.id).in_(device_ids))
    return list(session.exec(statement).all())

def search(
    session: Session,
    parsed: "ParsedQuery",  # type: ignore[name-defined]
    page: int = 1,
    limit: int = 50,
    workspace_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[tuple[Device, str | None]], int]:
    from src.domain.search import ParsedQuery

    stmt = build_search_statement()
    device_ids = get_workspace_device_ids(session, workspace_id, owner_id)
    stmt = apply_search_filters(stmt, parsed)
    stmt = apply_device_scope(stmt, session, col, device_ids, owner_id)

    count_stmt = sa_select(func.count()).select_from(stmt.subquery())
    total = int(session.execute(count_stmt).scalar_one())

    paginated = (
        stmt.offset((page - 1) * limit)
        .limit(limit)
        .order_by(Device.created_at)
    )
    rows = list(session.execute(paginated).all())
    return [(row[0], row[1]) for row in rows], total

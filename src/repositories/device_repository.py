"""Device repository — sole layer that holds a SQLModel Session for Device operations."""
import uuid
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from src.models.device import Device
from src.models.location import Location
from src.models.tag import DeviceTag, Tag

_SORT_EXPRESSIONS = {
    "name": lambda: col(Device.name),
    "-name": lambda: col(Device.name).desc(),
    "updated_at": lambda: col(Device.updated_at),
    "-updated_at": lambda: col(Device.updated_at).desc(),
    "created_at": lambda: col(Device.created_at),
    "-created_at": lambda: col(Device.created_at).desc(),
}


def create(session: Session, device: Device) -> Device:
    """Persist a new device and return the refreshed instance."""
    session.add(device)
    session.flush()
    session.refresh(device)
    return device


def get_by_id(session: Session, device_id: uuid.UUID) -> Device | None:
    """Return the device with the given primary key, or None."""
    return session.get(Device, device_id)


def get_all(
    session: Session,
    page: int = 1,
    limit: int = 50,
    sort: Optional[str] = None,
) -> tuple[list[Device], int]:
    """Return a paginated list of devices and the total count.

    Args:
        sort: Optional sort key. Valid values: name, -name, updated_at, -updated_at,
              created_at, -created_at. Invalid values silently fall back to created_at ASC.
    """
    total = int(session.exec(select(func.count()).select_from(Device)).one())
    offset = (page - 1) * limit
    order_expr = (
        _SORT_EXPRESSIONS[sort]()
        if sort in _SORT_EXPRESSIONS
        else col(Device.created_at)
    )
    statement = select(Device).offset(offset).limit(limit).order_by(order_expr)
    items = list(session.exec(statement).all())
    return items, total


def get_all_for_export(session: Session) -> list[Device]:
    """Return all devices ordered by created_at ASC (no pagination)."""
    statement = select(Device).order_by(col(Device.created_at))
    return list(session.exec(statement).all())


def update(session: Session, device: Device) -> Device:
    """Persist changes to an already-fetched device and return it."""
    session.add(device)
    session.flush()
    session.refresh(device)
    return device


def delete(session: Session, device: Device) -> None:
    """Hard-delete a device record."""
    session.delete(device)
    session.flush()


def count(session: Session) -> int:
    """Return the total number of devices in the database."""
    result = session.exec(select(func.count()).select_from(Device)).one()
    return int(result)


def get_children(session: Session, parent_id: uuid.UUID) -> list[Device]:
    """Return child devices whose parent_id points to parent_id (HT-021).

    Ordered by name ASC so the UI renders a stable children list.
    """
    statement = (
        select(Device)
        .where(col(Device.parent_id) == parent_id)
        .order_by(col(Device.name))
    )
    return list(session.exec(statement).all())


def count_children(session: Session, parent_id: uuid.UUID) -> int:
    """Return the number of direct child devices for parent_id (HT-021)."""
    result = session.exec(
        select(func.count())
        .select_from(Device)
        .where(col(Device.parent_id) == parent_id)
    ).one()
    return int(result)


def get_parent_map(
    session: Session,
) -> dict[uuid.UUID, Optional[uuid.UUID]]:
    """Return a flat {id: parent_id} dict for all devices (HT-021).

    Used by the service layer to pass to detect_parent_cycle without
    exposing a DB session to the domain layer.
    """
    statement = select(Device.id, Device.parent_id)
    rows = session.exec(statement).all()
    return {row[0]: row[1] for row in rows}


def get_all_with_location(
    session: Session, page: int = 1, limit: int = 1000,
    sort: Optional[str] = None,
) -> tuple[list[tuple[Device, str | None]], int]:
    """LEFT JOIN devices onto locations; return (Device, location_name) pairs + total."""
    total = int(session.exec(select(func.count()).select_from(Device)).one())
    offset = (page - 1) * limit
    order_expr = (
        _SORT_EXPRESSIONS[sort]()
        if sort in _SORT_EXPRESSIONS
        else col(Device.created_at)
    )
    stmt = (
        sa_select(Device, Location.name)  # type: ignore[call-overload]
        .outerjoin(Location, Device.location_id == Location.id)
        .offset(offset)
        .limit(limit)
        .order_by(order_expr)
    )
    rows = list(session.execute(stmt).all())
    return [(row[0], row[1]) for row in rows], total


def get_all_names(session: Session) -> list[str]:
    """Return a flat list of all device names in the database."""
    statement = select(Device.name).order_by(col(Device.created_at))
    return list(session.exec(statement).all())


def search(
    session: Session,
    parsed: "ParsedQuery",  # type: ignore[name-defined]
    page: int = 1,
    limit: int = 50,
) -> tuple[list[tuple[Device, str | None]], int]:
    """Filter devices using a ParsedQuery and return (Device, location_name) pairs + total.

    All populated fields apply as AND conditions.
    Within each field, multiple values use OR (any-match).
    """
    from src.domain.search import ParsedQuery, to_sql_like
    from src.models.service import Service

    stmt = (
        sa_select(Device, Location.name)  # type: ignore[call-overload]
        .outerjoin(Location, Device.location_id == Location.id)
    )

    if parsed.types:
        stmt = stmt.where(or_(*[func.lower(col(Device.type)).ilike(v.lower()) for v in parsed.types]))

    if parsed.ip_patterns:
        stmt = stmt.where(or_(*[
            col(Device.ip).ilike(to_sql_like(v), escape="\\")
            for v in parsed.ip_patterns
        ]))

    if parsed.os_patterns:
        stmt = stmt.where(or_(*[
            col(Device.os).ilike(f"%{to_sql_like(v)}%", escape="\\")
            for v in parsed.os_patterns
        ]))

    if parsed.tags:
        tag_subq = (
            sa_select(DeviceTag.device_id)  # type: ignore[call-overload]
            .join(Tag, DeviceTag.tag_id == Tag.id)
            .where(or_(*[col(Tag.name).ilike(f"%{v}%") for v in parsed.tags]))
        ).scalar_subquery()
        stmt = stmt.where(col(Device.id).in_(tag_subq))

    if parsed.location_patterns:
        stmt = stmt.where(or_(*[
            col(Location.name).ilike(f"%{to_sql_like(v)}%", escape="\\")
            for v in parsed.location_patterns
        ]))

    if parsed.service_patterns:
        svc_subq = (
            sa_select(Service.device_id)  # type: ignore[call-overload]
            .where(or_(*[
                col(Service.name).ilike(f"%{to_sql_like(v)}%", escape="\\")
                for v in parsed.service_patterns
            ]))
        ).scalar_subquery()
        stmt = stmt.where(col(Device.id).in_(svc_subq))

    if parsed.free_text:
        ft = f"%{parsed.free_text}%"
        stmt = stmt.where(or_(
            col(Device.name).ilike(ft),
            col(Device.ip).ilike(ft),
            col(Device.os).ilike(ft),
            col(Device.notes).ilike(ft),
            col(Location.name).ilike(ft),
        ))

    count_stmt = sa_select(func.count()).select_from(stmt.subquery())
    total = int(session.execute(count_stmt).scalar_one())

    paginated = (
        stmt.offset((page - 1) * limit)
        .limit(limit)
        .order_by(Device.created_at)
    )
    rows = list(session.execute(paginated).all())
    return [(row[0], row[1]) for row in rows], total

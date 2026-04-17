"""Tag repository — sole layer that holds a SQLModel Session for Tag operations."""
import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from src.models.tag import DeviceTag, Tag


def create(session: Session, tag: Tag) -> Tag:
    """Persist a new tag and return the refreshed instance."""
    session.add(tag)
    session.flush()
    session.refresh(tag)
    return tag


def get_by_id(session: Session, tag_id: uuid.UUID) -> Tag | None:
    """Return the tag with the given primary key, or None."""
    return session.get(Tag, tag_id)


def get_by_name_normalized(session: Session, normalized_name: str) -> Tag | None:
    """Return a tag whose LOWER(name) equals normalized_name, or None."""
    stmt = select(Tag).where(func.lower(Tag.name) == normalized_name)
    return session.exec(stmt).first()


def get_all_with_counts(session: Session) -> list[tuple[Tag, int]]:
    """Return (Tag, device_count) pairs ordered by Tag.name ASC."""
    stmt = (
        sa_select(Tag, func.count(DeviceTag.tag_id).label("device_count"))  # type: ignore[call-overload, arg-type]
        .outerjoin(DeviceTag, Tag.id == DeviceTag.tag_id)  # type: ignore[arg-type]
        .group_by(Tag.id)  # type: ignore[arg-type]
        .order_by(Tag.name)
    )
    rows = list(session.execute(stmt).all())
    return [(row[0], row[1]) for row in rows]


def update(session: Session, tag: Tag) -> Tag:
    """Persist changes to an already-fetched tag and return it."""
    session.add(tag)
    session.flush()
    session.refresh(tag)
    return tag


def delete(session: Session, tag: Tag) -> None:
    """Hard-delete a tag; DB CASCADE removes device_tags rows."""
    session.delete(tag)
    session.flush()


def get_all(session: Session) -> list[Tag]:
    """Return all tags ordered by created_at ASC."""
    stmt = select(Tag).order_by(col(Tag.created_at))
    return list(session.exec(stmt).all())


def get_all_device_tags(session: Session) -> list[DeviceTag]:
    """Return all device-tag associations."""
    stmt = select(DeviceTag)
    return list(session.exec(stmt).all())


def attach_to_device(
    session: Session, device_id: uuid.UUID, tag_id: uuid.UUID
) -> None:
    """Idempotently attach a tag to a device.

    Uses an atomic upsert to avoid check-then-insert races under concurrency.
    """
    values = {"device_id": device_id, "tag_id": tag_id}
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        session.execute(
            pg_insert(DeviceTag)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["device_id", "tag_id"])
        )
    else:
        session.execute(
            sqlite_insert(DeviceTag)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["device_id", "tag_id"])
        )
    session.flush()


def detach_from_device(
    session: Session, device_id: uuid.UUID, tag_id: uuid.UUID
) -> None:
    """Remove tag association; no-op if association does not exist."""
    stmt = select(DeviceTag).where(
        DeviceTag.device_id == device_id,
        DeviceTag.tag_id == tag_id,
    )
    assoc = session.exec(stmt).first()
    if assoc is not None:
        session.delete(assoc)
        session.flush()


def get_by_device(session: Session, device_id: uuid.UUID) -> list[Tag]:
    """Return all tags for a device, ordered by Tag.name ASC."""
    stmt = (
        select(Tag)
        .join(DeviceTag, Tag.id == DeviceTag.tag_id)  # type: ignore[arg-type]
        .where(DeviceTag.device_id == device_id)
        .order_by(Tag.name)
    )
    return list(session.exec(stmt).all())


def get_by_device_ids(
    session: Session, device_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Tag]]:
    """Return tags grouped by device_id for the provided device IDs."""
    if not device_ids:
        return {}
    grouped: dict[uuid.UUID, list[Tag]] = {device_id: [] for device_id in device_ids}
    stmt = (
        sa_select(DeviceTag.device_id, Tag)  # type: ignore[call-overload]
        .join(Tag, Tag.id == DeviceTag.tag_id)
        .where(col(DeviceTag.device_id).in_(device_ids))
        .order_by(Tag.name)
    )
    rows = list(session.execute(stmt).all())
    for row in rows:
        grouped[row[0]].append(row[1])
    return grouped

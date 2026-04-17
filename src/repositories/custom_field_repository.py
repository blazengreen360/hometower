"""Custom field repository — sole layer that holds a SQLModel Session for CustomField ops."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.custom_field import CustomField


def create(session: Session, cf: CustomField) -> CustomField:
    """Persist a new custom field and return the refreshed instance."""
    session.add(cf)
    session.flush()
    session.refresh(cf)
    return cf


def get_by_id(session: Session, cf_id: uuid.UUID) -> CustomField | None:
    """Return the custom field with the given primary key, or None."""
    return session.get(CustomField, cf_id)


def get_by_device(session: Session, device_id: uuid.UUID) -> list[CustomField]:
    """Return all custom fields for a device, ordered by created_at ASC."""
    stmt = (
        select(CustomField)
        .where(CustomField.device_id == device_id)
        .order_by(col(CustomField.created_at))
    )
    return list(session.exec(stmt).all())


def get_by_device_and_key_normalized(
    session: Session, device_id: uuid.UUID, normalized_key: str
) -> CustomField | None:
    """Return the custom field for a device whose LOWER(key) equals normalized_key, or None."""
    stmt = select(CustomField).where(
        CustomField.device_id == device_id,
        func.lower(CustomField.key) == normalized_key,
    )
    return session.exec(stmt).first()


def update(session: Session, cf: CustomField) -> CustomField:
    """Persist changes to an already-fetched custom field and return it."""
    cf.updated_at = datetime.now(timezone.utc)
    session.add(cf)
    session.flush()
    session.refresh(cf)
    return cf


def get_all(session: Session) -> list[CustomField]:
    """Return all custom fields ordered by created_at ASC."""
    stmt = select(CustomField).order_by(col(CustomField.created_at))
    return list(session.exec(stmt).all())


def delete(session: Session, cf: CustomField) -> None:
    """Hard-delete a custom field."""
    session.delete(cf)
    session.flush()


def get_by_device_ids(
    session: Session, device_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[CustomField]]:
    """Return custom fields grouped by device_id for the provided device IDs."""
    if not device_ids:
        return {}
    grouped: dict[uuid.UUID, list[CustomField]] = {
        device_id: [] for device_id in device_ids
    }
    stmt = (
        select(CustomField)
        .where(col(CustomField.device_id).in_(device_ids))
        .order_by(col(CustomField.created_at))
    )
    rows = list(session.exec(stmt).all())
    for cf in rows:
        grouped[cf.device_id].append(cf)
    return grouped

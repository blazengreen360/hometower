"""Device repository — sole layer that holds a SQLModel Session for Device operations."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.device import Device


def create(session: Session, device: Device) -> Device:
    """Persist a new device and return the refreshed instance."""
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def get_by_id(session: Session, device_id: uuid.UUID) -> Device | None:
    """Return the device with the given primary key, or None."""
    return session.get(Device, device_id)


def get_all(
    session: Session, page: int = 1, limit: int = 50
) -> tuple[list[Device], int]:
    """Return a paginated list of devices and the total count."""
    total = int(session.exec(select(func.count()).select_from(Device)).one())
    offset = (page - 1) * limit
    statement = (
        select(Device).offset(offset).limit(limit).order_by(col(Device.created_at))
    )
    items = list(session.exec(statement).all())
    return items, total


def update(session: Session, device: Device) -> Device:
    """Persist changes to an already-fetched device and return it."""
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def delete(session: Session, device: Device) -> None:
    """Hard-delete a device record."""
    session.delete(device)
    session.commit()


def count(session: Session) -> int:
    """Return the total number of devices in the database."""
    result = session.exec(select(func.count()).select_from(Device)).one()
    return int(result)

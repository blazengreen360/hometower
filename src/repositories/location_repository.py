"""Location repository — sole layer that holds a SQLModel Session for Location operations."""
import uuid
from typing import Optional

from sqlmodel import Session, col, select

from src.models.device import Device
from src.models.location import Location
from src.models.types import LocationType


def create(session: Session, location: Location) -> Location:
    """Persist a new location and return the refreshed instance."""
    session.add(location)
    session.flush()
    session.refresh(location)
    return location


def get_by_id(session: Session, location_id: uuid.UUID) -> Location | None:
    """Return the location with the given primary key, or None."""
    return session.get(Location, location_id)


def get_all(
    session: Session, type: Optional[LocationType] = None
) -> list[Location]:
    """Return all locations, optionally filtered by type."""
    statement = select(Location)
    if type is not None:
        statement = statement.where(col(Location.type) == type)
    return list(session.exec(statement).all())


def get_ancestors(session: Session, location_id: uuid.UUID) -> list[Location]:
    """Walk the parent chain from location_id and return ordered nearest→root.

    Raises ValueError if hierarchy depth exceeds 50.
    """
    ancestors: list[Location] = []
    current_id: Optional[uuid.UUID] = location_id
    depth = 0

    # Start from the location itself to get its parent_id
    current = session.get(Location, current_id)
    if current is None:
        return ancestors
    current_id = current.parent_id

    while current_id is not None:
        if depth >= 50:
            raise ValueError("Location hierarchy depth exceeds limit")
        parent = session.get(Location, current_id)
        if parent is None:
            break
        ancestors.append(parent)
        current_id = parent.parent_id
        depth += 1

    return ancestors


def get_devices_at_location(session: Session, location_id: uuid.UUID) -> list[Device]:
    """Return all devices assigned to the given location."""
    statement = select(Device).where(col(Device.location_id) == location_id)
    return list(session.exec(statement).all())


def get_children(session: Session, location_id: uuid.UUID) -> list[Location]:
    """Return child locations whose parent_id points to location_id."""
    statement = select(Location).where(col(Location.parent_id) == location_id)
    return list(session.exec(statement).all())


def get_parent_map(session: Session) -> dict[uuid.UUID, Optional[uuid.UUID]]:
    """Return a flat {id: parent_id} dict for all locations.

    Used by the service layer to pass to detect_cycle without a DB session
    in the domain layer.
    """
    statement = select(Location.id, Location.parent_id)
    rows = session.exec(statement).all()
    return {row[0]: row[1] for row in rows}


def update(session: Session, location: Location) -> Location:
    """Persist changes to an already-fetched location and return it."""
    session.add(location)
    session.flush()
    session.refresh(location)
    return location


def delete(session: Session, location: Location) -> None:
    """Hard-delete a location record."""
    session.delete(location)
    session.flush()

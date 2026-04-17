"""Power repository for settings and summary snapshot reads (HT-044)."""
import uuid
from typing import TypedDict

from sqlmodel import Session, select

from src.models.device import Device
from src.models.location import Location
from src.models.power_settings import PowerSettings


class PowerDeviceSnapshot(TypedDict):
    location_id: uuid.UUID | None
    power_watts: int | None


class PowerLocationSnapshot(TypedDict):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None


def get_settings(session: Session) -> PowerSettings | None:
    """Return global power settings row if present."""
    return session.get(PowerSettings, "global")


def create_settings(session: Session, settings_row: PowerSettings) -> PowerSettings:
    """Insert power settings row and return refreshed instance."""
    session.add(settings_row)
    session.flush()
    session.refresh(settings_row)
    return settings_row


def update_settings(session: Session, settings_row: PowerSettings) -> PowerSettings:
    """Persist changes to settings row and return refreshed instance."""
    session.add(settings_row)
    session.flush()
    session.refresh(settings_row)
    return settings_row


def list_device_rows(session: Session) -> list[PowerDeviceSnapshot]:
    """Return power-summary snapshots from devices table."""
    rows = session.exec(select(Device.location_id, Device.power_watts)).all()
    return [
        {"location_id": location_id, "power_watts": power_watts}
        for location_id, power_watts in rows
    ]


def list_location_rows(session: Session) -> list[PowerLocationSnapshot]:
    """Return hierarchy snapshots from locations table."""
    rows = session.exec(select(Location.id, Location.name, Location.parent_id)).all()
    return [
        {"id": location_id, "name": name, "parent_id": parent_id}
        for location_id, name, parent_id in rows
    ]
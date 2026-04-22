"""Helper functions for device write-path validation."""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import devices as device_domain
from src.models.device import Device, DeviceUpdate
from src.repositories import device_repository, location_repository


def assert_location_exists(location_id: uuid.UUID, session: Session) -> None:
    location = location_repository.get_by_id(session, location_id)
    if location is None:
        raise HTTPException(status_code=400, detail="Location not found")


def assert_parent_exists(
    parent_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    parent = device_repository.get_by_id(session, parent_id, owner_id=owner_id)
    if parent is None:
        raise HTTPException(status_code=400, detail="Parent device not found")


def raise_device_conflict(exc: IntegrityError, session: Session, detail: str) -> None:
    session.rollback()
    raise HTTPException(status_code=409, detail=detail) from exc


def prepare_device_update_data(
    device_id: uuid.UUID,
    device: Device,
    data: DeviceUpdate,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> dict[str, object]:
    update_data = data.model_dump(exclude_unset=True)
    expected_version = update_data.pop("version")
    if expected_version != device.version:
        raise HTTPException(
            status_code=409,
            detail="Conflict: device was modified by another request",
        )
    if "ip" in update_data:
        update_data["ip"] = device_domain.validate_ip(update_data["ip"])
    if "mac" in update_data:
        update_data["mac"] = device_domain.validate_mac(update_data["mac"])
    _validate_location_update(update_data, session)
    _validate_parent_update(device_id, update_data, session, owner_id)
    return update_data


def _validate_location_update(update_data: dict[str, object], session: Session) -> None:
    location_id = update_data.get("location_id")
    if isinstance(location_id, uuid.UUID):
        assert_location_exists(location_id, session)


def _validate_parent_update(
    device_id: uuid.UUID,
    update_data: dict[str, object],
    session: Session,
    owner_id: uuid.UUID | None,
) -> None:
    parent_id = update_data.get("parent_id")
    if not isinstance(parent_id, uuid.UUID):
        return
    if parent_id == device_id:
        raise HTTPException(status_code=400, detail="Device cannot be its own parent")
    assert_parent_exists(parent_id, session, owner_id=owner_id)
    parent_map = device_repository.get_parent_map(session, owner_id=owner_id)
    if device_domain.detect_parent_cycle(device_id, parent_id, parent_map):
        raise HTTPException(status_code=400, detail="Circular containment detected")
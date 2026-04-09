"""Device service — orchestrates domain logic and device repository."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from src.domain import devices as device_domain
from src.models.device import Device, DeviceCreate, DeviceUpdate
from src.repositories import device_repository
from src.utils.logger import logger


def create(data: DeviceCreate, session: Session) -> Device:
    """Validate and persist a new device."""
    validated_ip = device_domain.validate_ip(data.ip)
    validated_mac = device_domain.validate_mac(data.mac)
    device = Device(
        name=data.name,
        type=data.type,
        ip=validated_ip,
        mac=validated_mac,
        os=data.os,
        notes=data.notes,
        location_id=data.location_id,
    )
    result = device_repository.create(session, device)
    logger.info("Device created: id={} name={}", result.id, result.name)
    return result


def get_by_id(device_id: uuid.UUID, session: Session) -> Device:
    """Return the device or raise HTTP 404."""
    device = device_repository.get_by_id(session, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def get_all(
    session: Session, page: int, limit: int
) -> tuple[list[Device], int]:
    """Return a paginated list of devices and total count."""
    return device_repository.get_all(session, page, limit)


def update(device_id: uuid.UUID, data: DeviceUpdate, session: Session) -> Device:
    """Partially update a device; raise HTTP 404 if not found."""
    device = device_repository.get_by_id(session, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    update_data = data.model_dump(exclude_unset=True)
    if "ip" in update_data:
        update_data["ip"] = device_domain.validate_ip(update_data["ip"])
    if "mac" in update_data:
        update_data["mac"] = device_domain.validate_mac(update_data["mac"])

    for field, value in update_data.items():
        setattr(device, field, value)

    device.updated_at = datetime.now(timezone.utc)
    result = device_repository.update(session, device)
    logger.info("Device updated: id={} name={}", result.id, result.name)
    return result


def _count_device_connections(device_id: uuid.UUID, session: Session) -> int:
    """Count active connections for a device. Returns 0 until connections table exists (HT-004)."""
    # TODO(HT-004): Replace with connection_repository.count_by_device()
    return 0


def delete(device_id: uuid.UUID, session: Session) -> None:
    """Delete a device; raise HTTP 404 if not found, HTTP 400 if connections exist."""
    device = device_repository.get_by_id(session, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    count = _count_device_connections(device_id, session)
    try:
        device_domain.validate_device_deletable(count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    device_repository.delete(session, device)
    logger.info("Device deleted: id={}", device_id)

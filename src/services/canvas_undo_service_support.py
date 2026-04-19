"""Helper mappers for canvas undo snapshot persistence."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.canvas_undo import (
    PublishedConnectionSnapshot,
    PublishedDeviceDeleteSnapshot,
    PublishedDeviceSnapshot,
)
from src.models.connection import Connection
from src.models.device import Device

_RESTORE_OWNER_KEY = "__hometower_owner_id"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_device_snapshot(device: Device) -> PublishedDeviceSnapshot:
    return PublishedDeviceSnapshot(
        id=device.id,
        name=device.name,
        type=device.type,
        status=device.status,
        ip=device.ip,
        mac=device.mac,
        os=device.os,
        notes=device.notes,
        location_id=device.location_id,
        parent_id=device.parent_id,
        version=device.version,
    )


def _to_connection_snapshot(connection: Connection) -> PublishedConnectionSnapshot:
    return PublishedConnectionSnapshot(
        id=connection.id,
        source_id=connection.source_id,
        target_id=connection.target_id,
        type=connection.type,
        label=connection.label,
    )


def _snapshot_node_with_owner(
    node: dict[str, object],
    owner_id: uuid.UUID | None,
) -> dict[str, object]:
    snapshot = dict(node)
    if owner_id is None:
        return snapshot
    snapshot[_RESTORE_OWNER_KEY] = str(owner_id)
    return snapshot


def _restore_node_without_owner(node: dict[str, object]) -> dict[str, object]:
    restored = dict(node)
    restored.pop(_RESTORE_OWNER_KEY, None)
    return restored


def _resolve_snapshot_owner_id(
    snapshot: PublishedDeviceDeleteSnapshot,
) -> uuid.UUID | None:
    for placement in snapshot.placements:
        raw_owner_id = placement.node.get(_RESTORE_OWNER_KEY)
        if raw_owner_id is None:
            continue
        try:
            return uuid.UUID(str(raw_owner_id))
        except ValueError:
            continue
    return None


def _raise_restore_conflict(exc: IntegrityError, session: Session) -> None:
    session.rollback()
    message = str(exc.orig)
    normalized = message.lower()
    if "ix_connections_unique_pair" in normalized:
        detail = "Connection already exists between these devices"
    elif "devices_pkey" in normalized or "unique constraint failed: devices.id" in normalized:
        detail = "Device ID already exists"
    else:
        detail = "Canvas restore conflict"
    raise HTTPException(status_code=409, detail=detail) from exc
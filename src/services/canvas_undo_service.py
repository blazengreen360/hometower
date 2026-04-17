"""Service helpers for canvas-specific undo/redo API mutations (HT-032)."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import devices as device_domain
from src.models.canvas_undo import (
    DiagramPlacementSnapshot,
    DiagramVersionRef,
    PublishedConnectionSnapshot,
    PublishedDeviceCanvasDeleteResult,
    PublishedDeviceCanvasRestoreResult,
    PublishedDeviceDeleteSnapshot,
    PublishedDeviceSnapshot,
)
from src.models.connection import Connection
from src.models.device import Device
from src.repositories import connection_repository, device_repository, diagram_repository
from src.utils.logger import logger


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


def delete_published_device_for_canvas(
    device_id: uuid.UUID,
    session: Session,
) -> PublishedDeviceCanvasDeleteResult:
    """Capture a restore snapshot, delete the device, and return modified diagram versions."""
    device = device_repository.get_by_id(session, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    child_count = device_repository.count_children(session, device_id)
    try:
        device_domain.validate_device_no_children(child_count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    device_id_str = str(device_id)
    connections = connection_repository.get_by_device(session, device_id)
    connection_snapshots = [_to_connection_snapshot(conn) for conn in connections]

    placements: list[DiagramPlacementSnapshot] = []
    modified_diagrams: list[DiagramVersionRef] = []

    for layout in diagram_repository.get_all_layouts(session):
        cytoscape_json = layout.cytoscape_json
        if not isinstance(cytoscape_json, dict):
            continue

        node_snapshot, was_collapsed = device_domain.extract_device_view_snapshot(
            cytoscape_json,
            device_id_str,
        )
        if node_snapshot is None:
            continue

        placements.append(
            DiagramPlacementSnapshot(
                diagram_id=layout.id,
                node=node_snapshot,
                was_collapsed=was_collapsed,
            )
        )

        filtered_json, changed = device_domain.filter_device_from_cytoscape_json(
            cytoscape_json,
            device_id_str,
        )
        if not changed:
            continue

        layout.cytoscape_json = filtered_json
        layout.version += 1
        layout.updated_at = _utcnow()
        diagram_repository.update(session, layout)
        modified_diagrams.append(
            DiagramVersionRef(diagram_id=layout.id, version=layout.version)
        )

    device_snapshot = _to_device_snapshot(device)

    try:
        connection_repository.delete_by_device(session, device_id)
        device_repository.delete(session, device)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Canvas delete conflict") from exc

    logger.info("Canvas delete snapshot created for device={} diagrams={}", device_id, len(modified_diagrams))

    return PublishedDeviceCanvasDeleteResult(
        snapshot=PublishedDeviceDeleteSnapshot(
            device=device_snapshot,
            connections=connection_snapshots,
            placements=placements,
        ),
        modified_diagrams=modified_diagrams,
    )


def restore_published_device_for_canvas(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
) -> PublishedDeviceCanvasRestoreResult:
    """Restore a previously deleted published device and its placements in one transaction."""
    if device_repository.get_by_id(session, snapshot.device.id) is not None:
        raise HTTPException(status_code=409, detail="Device ID already exists")

    restored_device = Device(
        id=snapshot.device.id,
        name=snapshot.device.name,
        type=snapshot.device.type,
        status=snapshot.device.status,
        ip=snapshot.device.ip,
        mac=snapshot.device.mac,
        os=snapshot.device.os,
        notes=snapshot.device.notes,
        location_id=snapshot.device.location_id,
        parent_id=snapshot.device.parent_id,
        version=snapshot.device.version,
    )

    modified_diagrams: list[DiagramVersionRef] = []

    try:
        device_repository.create(session, restored_device)

        for connection_snapshot in snapshot.connections:
            restored_connection = Connection(
                id=connection_snapshot.id,
                source_id=connection_snapshot.source_id,
                target_id=connection_snapshot.target_id,
                type=connection_snapshot.type,
                label=connection_snapshot.label,
            )
            connection_repository.create(session, restored_connection)

        for placement in snapshot.placements:
            layout = diagram_repository.get_by_id_for_update(session, placement.diagram_id)
            if layout is None:
                session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Cannot restore device placement: "
                        f"diagram {placement.diagram_id} no longer exists"
                    ),
                )

            cytoscape_json = layout.cytoscape_json
            if not isinstance(cytoscape_json, dict):
                session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Cannot restore device placement: "
                        f"diagram {placement.diagram_id} has invalid layout JSON"
                    ),
                )

            restored_json, changed = device_domain.restore_device_to_cytoscape_json(
                cytoscape_json,
                placement.node,
                placement.was_collapsed,
            )
            if changed:
                layout.cytoscape_json = restored_json
                layout.version += 1
                layout.updated_at = _utcnow()
                diagram_repository.update(session, layout)

            modified_diagrams.append(
                DiagramVersionRef(diagram_id=layout.id, version=layout.version)
            )

        session.commit()
    except IntegrityError as exc:
        _raise_restore_conflict(exc, session)

    logger.info(
        "Canvas restore applied for device={} diagrams={}",
        snapshot.device.id,
        len(modified_diagrams),
    )

    return PublishedDeviceCanvasRestoreResult(modified_diagrams=modified_diagrams)

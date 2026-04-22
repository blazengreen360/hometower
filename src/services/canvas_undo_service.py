"""Service helpers for canvas-specific undo/redo API mutations (HT-032)."""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import devices as device_domain
from src.models.canvas_undo import (
    DiagramPlacementSnapshot,
    DiagramVersionRef,
    PublishedDeviceCanvasDeleteResult,
    PublishedDeviceCanvasRestoreResult,
    PublishedDeviceDeleteSnapshot,
)
from src.repositories import connection_repository, device_repository, diagram_repository, topology_history_repository
from src.services.canvas_undo_inventory_support import capture_related_snapshot_data
from src.services.canvas_undo_inventory_support import delete_snapshot_inventory
from src.services.canvas_undo_inventory_support import restage_restored_attachments
from src.services.canvas_undo_inventory_support import restore_snapshot_attachments
from src.services.canvas_undo_inventory_support import restore_snapshot_inventory
from src.services.canvas_undo_inventory_support import rollback_staged_attachments
from src.services.canvas_undo_inventory_support import stage_snapshot_attachments
from src.services.canvas_undo_service_restore_support import _assert_canvas_restore_allowed
from src.services.canvas_undo_service_restore_support import _build_restore_token
from src.services.canvas_undo_service_restore_support import _build_restored_device
from src.services.canvas_undo_service_restore_support import _raise_restore_conflict
from src.services.canvas_undo_service_restore_support import _restore_snapshot_connections
from src.services.canvas_undo_service_restore_support import _restore_snapshot_placements
from src.services.canvas_undo_service_support import _snapshot_node_with_owner
from src.services.canvas_undo_service_support import _to_connection_snapshot
from src.services.canvas_undo_service_support import _to_device_snapshot
from src.services.canvas_undo_service_support import _utcnow
from src.utils.logger import logger


def _capture_device_placements_and_remove_from_layouts(
    device_id_str: str,
    device_owner_id: uuid.UUID | None,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[DiagramPlacementSnapshot], list[DiagramVersionRef]]:
    placements: list[DiagramPlacementSnapshot] = []
    modified_diagrams: list[DiagramVersionRef] = []
    layouts = (
        diagram_repository.get_all_layouts_for_owner(session, owner_id)
        if owner_id is not None
        else diagram_repository.get_all_layouts(session)
    )
    immutable_diagram_ids = topology_history_repository.get_immutable_diagram_ids(
        session,
        {layout.id for layout in layouts},
    )

    for layout in layouts:
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
                node=_snapshot_node_with_owner(node_snapshot, device_owner_id),
                was_collapsed=was_collapsed,
            )
        )

        filtered_json, changed = device_domain.filter_device_from_cytoscape_json(
            cytoscape_json,
            device_id_str,
        )
        if layout.id in immutable_diagram_ids:
            continue
        if not changed:
            continue

        layout.cytoscape_json = filtered_json
        layout.version += 1
        layout.updated_at = _utcnow()
        diagram_repository.update(session, layout)
        modified_diagrams.append(DiagramVersionRef(diagram_id=layout.id, version=layout.version))

    return placements, modified_diagrams


def delete_published_device_for_canvas(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> PublishedDeviceCanvasDeleteResult:
    """Capture a restore snapshot, delete the device, and return modified diagram versions."""
    device = device_repository.get_by_id(session, device_id, owner_id=owner_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    child_count = device_repository.count_children(session, device_id, owner_id=owner_id)
    try:
        device_domain.validate_device_no_children(child_count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    device_id_str = str(device_id)
    connections = connection_repository.get_by_device(session, device_id)
    connection_snapshots = [_to_connection_snapshot(conn) for conn in connections]
    (
        tag_ids,
        custom_fields,
        service_snapshots,
        service_dependencies,
        network_memberships,
        attachments,
    ) = capture_related_snapshot_data(device_id, session)
    attachment_stash_id = uuid.uuid4() if attachments else None

    placements, modified_diagrams = _capture_device_placements_and_remove_from_layouts(
        device_id_str,
        device.owner_id,
        session,
        owner_id=owner_id,
    )

    snapshot = PublishedDeviceDeleteSnapshot(
        device=_to_device_snapshot(device),
        connections=connection_snapshots,
        placements=placements,
        tag_ids=tag_ids,
        custom_fields=custom_fields,
        services=service_snapshots,
        service_dependencies=service_dependencies,
        network_memberships=network_memberships,
        attachments=attachments,
        attachment_stash_id=attachment_stash_id,
    )
    snapshot.restore_token = _build_restore_token(snapshot, owner_id, device.owner_id)

    stage_snapshot_attachments(device_id, attachment_stash_id, bool(attachments))

    try:
        delete_snapshot_inventory(snapshot, session)
        connection_repository.delete_by_device(session, device_id)
        device_repository.delete(session, device)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        rollback_staged_attachments(device_id, attachment_stash_id)
        raise HTTPException(status_code=409, detail="Canvas delete conflict") from exc

    logger.info("Canvas delete snapshot created for device={} diagrams={}", device_id, len(modified_diagrams))
    return PublishedDeviceCanvasDeleteResult(snapshot=snapshot, modified_diagrams=modified_diagrams)


def restore_published_device_for_canvas(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> PublishedDeviceCanvasRestoreResult:
    """Restore a previously deleted published device and its placements in one transaction."""
    snapshot_owner_id = _assert_canvas_restore_allowed(snapshot, session, owner_id)
    restored_device = _build_restored_device(snapshot, snapshot_owner_id)
    modified_diagrams: list[DiagramVersionRef] = []
    attachments_restored = False

    try:
        device_repository.create(session, restored_device)
        restore_snapshot_inventory(snapshot, session)
        _restore_snapshot_connections(snapshot, session)
        modified_diagrams = _restore_snapshot_placements(snapshot, session, owner_id)
        attachments_restored = restore_snapshot_attachments(snapshot)
        session.commit()
    except IntegrityError as exc:
        if attachments_restored:
            restage_restored_attachments(snapshot.device.id, snapshot.attachment_stash_id)
        _raise_restore_conflict(exc, session)
    except HTTPException:
        if attachments_restored:
            restage_restored_attachments(snapshot.device.id, snapshot.attachment_stash_id)
        session.rollback()
        raise

    logger.info(
        "Canvas restore applied for device={} diagrams={}",
        snapshot.device.id,
        len(modified_diagrams),
    )
    return PublishedDeviceCanvasRestoreResult(modified_diagrams=modified_diagrams)

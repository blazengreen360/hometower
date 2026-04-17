"""Ghost placeholder contract and reconciliation service for HT-075."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import topology_history as topology_history_domain
from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.topology_editor import TopologySaveVersionResponse
from src.models.topology_history_entry import TopologyHistoryEntry
from src.models.types import DeviceStatus, DeviceType, Role
from src.repositories import (
    device_repository,
    diagram_repository,
    topology_history_repository,
    topology_personal_draft_repository,
    topology_repository,
)
from src.services import topology_service
from src.services.topology_editor_common import (
    clone_json,
    empty_canvas_json,
    raise_conflict,
    resolve_current_diagram,
    resolve_snapshot_name,
    utcnow,
)
from src.utils.logger import logger


def _next_immutable_diagram_version(current: DiagramLayout | None) -> int:
    return 1 if current is None else current.version + 1


def _existing_device_ids(session: Session) -> set[str]:
    return {str(device.id) for device in device_repository.get_all_for_export(session)}


def with_ghost_contract(
    cytoscape_json: dict[str, object],
    topology_id: uuid.UUID,
    role: Role,
    session: Session,
) -> dict[str, object]:
    payload = clone_json(cytoscape_json)
    payload.pop("restore_summary", None)
    ghosted_payload, missing = topology_history_domain.synthesize_ghost_placeholders(
        payload,
        _existing_device_ids(session),
    )
    if not missing:
        return ghosted_payload
    summary = topology_history_domain.build_ghost_restore_summary(missing, role)
    ghost_recovery = summary.get("ghost_recovery")
    if isinstance(ghost_recovery, dict):
        ghost_recovery["endpoint_templates"] = {
            "recreate": f"/api/topologies/{topology_id}/ghosts/{{ghost_id}}/recreate",
            "map": f"/api/topologies/{topology_id}/ghosts/{{ghost_id}}/map",
        }
    ghosted_payload["restore_summary"] = summary
    return ghosted_payload


def _resolve_current_topology_diagram(topology_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> tuple[Topology, DiagramLayout]:
    topology = topology_service.get_by_id(topology_id, owner_id, session)
    current = resolve_current_diagram(
        topology.id,
        topology.current_diagram_id,
        session,
        get_diagram=diagram_repository.get_by_id,
    )
    if current is None:
        raise HTTPException(status_code=404, detail="Current topology snapshot not found")
    return topology, current


def _ensure_base_diagram_version(current: DiagramLayout, base_diagram_version: int | None) -> None:
    if base_diagram_version is not None and base_diagram_version != current.version:
        raise HTTPException(status_code=409, detail="Conflict: topology version is stale")


def _persist_reconciled_version(topology: Topology, current: DiagramLayout, user_id: uuid.UUID, snapshot_name: str, action: str, cytoscape_json: dict[str, object], session: Session) -> tuple[DiagramLayout, TopologyHistoryEntry]:
    diagram = DiagramLayout(
        name=snapshot_name,
        topology_id=topology.id,
        cytoscape_json=cytoscape_json,
        version=_next_immutable_diagram_version(current),
    )
    saved_diagram = diagram_repository.create(session, diagram)
    history_entry = topology_history_repository.create(
        session,
        TopologyHistoryEntry(
            topology_id=topology.id,
            diagram_id=saved_diagram.id,
            snapshot_name=snapshot_name,
            action=action,
            created_by=user_id,
        ),
    )
    topology.current_diagram_id = saved_diagram.id
    topology.updated_at = utcnow()
    topology_repository.update(session, topology)
    draft = topology_personal_draft_repository.get_by_topology_and_user(session, topology.id, user_id)
    if draft is not None:
        topology_personal_draft_repository.delete(session, draft)
    return saved_diagram, history_entry


def _resolve_recreated_device_type(raw_type: str) -> DeviceType:
    try:
        return DeviceType(raw_type)
    except ValueError:
        return DeviceType.Server


def recreate_ghost_as_new_device(topology_id: uuid.UUID, ghost_id: uuid.UUID, owner_id: uuid.UUID, user_id: uuid.UUID, role: Role, base_diagram_version: int | None, session: Session) -> TopologySaveVersionResponse:
    topology, current = _resolve_current_topology_diagram(topology_id, owner_id, session)
    _ensure_base_diagram_version(current, base_diagram_version)
    if device_repository.get_by_id(session, ghost_id) is not None:
        raise HTTPException(status_code=409, detail="Device still exists in inventory")

    current_json = current.cytoscape_json if isinstance(current.cytoscape_json, dict) else empty_canvas_json()
    ghost_meta = topology_history_domain.get_missing_device_metadata(current_json, str(ghost_id))
    if ghost_meta is None:
        raise HTTPException(status_code=404, detail="Ghost placeholder not found")

    recreated_device_id = uuid.uuid4()
    reconciled_json, changed = topology_history_domain.replace_ghost_with_live_device(current_json, str(ghost_id), str(recreated_device_id))
    if not changed:
        raise HTTPException(status_code=404, detail="Ghost placeholder not found")

    recreated_device = Device(
        id=recreated_device_id,
        name=ghost_meta["name"],
        type=_resolve_recreated_device_type(ghost_meta["device_type"]),
        status=DeviceStatus.Planned,
        notes=f"Recreated from topology ghost placeholder {ghost_id}",
    )
    snapshot_name = resolve_snapshot_name(f"Recreate ghost {str(ghost_id)[:8]}")
    try:
        device_repository.create(session, recreated_device)
        saved_diagram, history_entry = _persist_reconciled_version(
            topology,
            current,
            user_id,
            snapshot_name,
            "ghost_recreate",
            reconciled_json,
            session,
        )
        session.commit()
    except IntegrityError as exc:
        raise_conflict(exc, session, "Ghost recreate conflict")

    logger.info(
        "Topology ghost recreated: topology_id={} ghost_id={} device_id={} entry_id={}",
        topology.id,
        ghost_id,
        recreated_device_id,
        history_entry.id,
    )
    return TopologySaveVersionResponse(
        topology_id=topology.id,
        history_entry_id=history_entry.id,
        current_diagram_id=saved_diagram.id,
        current_diagram_version=saved_diagram.version,
        snapshot_name=history_entry.snapshot_name,
        action=history_entry.action,
        restored_from_history_entry_id=None,
        created_at=history_entry.created_at,
        draft_version=None,
        has_unsaved_changes=False,
        cytoscape_json=with_ghost_contract(saved_diagram.cytoscape_json, topology.id, role, session),
    )


def map_ghost_to_existing_device(topology_id: uuid.UUID, ghost_id: uuid.UUID, live_device_id: uuid.UUID, owner_id: uuid.UUID, user_id: uuid.UUID, role: Role, base_diagram_version: int | None, session: Session) -> TopologySaveVersionResponse:
    topology, current = _resolve_current_topology_diagram(topology_id, owner_id, session)
    _ensure_base_diagram_version(current, base_diagram_version)
    if device_repository.get_by_id(session, live_device_id) is None:
        raise HTTPException(status_code=404, detail="Target device not found")
    if device_repository.get_by_id(session, ghost_id) is not None:
        raise HTTPException(status_code=409, detail="Device still exists in inventory")

    current_json = current.cytoscape_json if isinstance(current.cytoscape_json, dict) else empty_canvas_json()
    reconciled_json, changed = topology_history_domain.replace_ghost_with_live_device(current_json, str(ghost_id), str(live_device_id))
    if not changed:
        raise HTTPException(status_code=404, detail="Ghost placeholder not found")

    snapshot_name = resolve_snapshot_name(f"Map ghost {str(ghost_id)[:8]}")
    try:
        saved_diagram, history_entry = _persist_reconciled_version(
            topology,
            current,
            user_id,
            snapshot_name,
            "ghost_map",
            reconciled_json,
            session,
        )
        session.commit()
    except IntegrityError as exc:
        raise_conflict(exc, session, "Ghost map conflict")

    logger.info(
        "Topology ghost mapped: topology_id={} ghost_id={} live_device_id={} entry_id={}",
        topology.id,
        ghost_id,
        live_device_id,
        history_entry.id,
    )
    return TopologySaveVersionResponse(
        topology_id=topology.id,
        history_entry_id=history_entry.id,
        current_diagram_id=saved_diagram.id,
        current_diagram_version=saved_diagram.version,
        snapshot_name=history_entry.snapshot_name,
        action=history_entry.action,
        restored_from_history_entry_id=None,
        created_at=history_entry.created_at,
        draft_version=None,
        has_unsaved_changes=False,
        cytoscape_json=with_ghost_contract(saved_diagram.cytoscape_json, topology.id, role, session),
    )

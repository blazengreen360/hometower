"""Topology history checkpoint and restore service (HT-072)."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.diagram import DiagramLayout
from src.models.topology_editor import (
    TopologyRestoreHistoryRequest,
    TopologySaveVersionRequest,
    TopologySaveVersionResponse,
)
from src.models.topology_history_entry import (
    PaginatedTopologyHistory,
    TopologyHistoryEntry,
    TopologyHistorySummary,
)
from src.models.types import Role
from src.repositories import (
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
from src.services.topology_editor_ghost_service import with_ghost_contract
from src.utils.logger import logger


def _next_immutable_diagram_version(current: DiagramLayout | None) -> int:
    if current is None:
        return 1
    return current.version + 1


def list_history(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    session: Session,
    page: int = 1,
    limit: int = 50,
) -> PaginatedTopologyHistory:
    """Return immutable history entries for a topology."""
    topology = topology_service.get_by_id(topology_id, owner_id, session)
    items, total = topology_history_repository.list_by_topology(
        session,
        topology.id,
        page,
        limit,
    )
    summaries = [
        TopologyHistorySummary(
            id=item.id,
            diagram_id=item.diagram_id,
            snapshot_name=item.snapshot_name,
            action=item.action,
            restored_from_history_entry_id=item.restored_from_history_entry_id,
            created_at=item.created_at,
            is_current=topology.current_diagram_id == item.diagram_id,
        )
        for item in items
    ]
    return PaginatedTopologyHistory(items=summaries, total=total, page=page, limit=limit)


def save_version(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    data: TopologySaveVersionRequest,
    session: Session,
) -> TopologySaveVersionResponse:
    """Persist an immutable history checkpoint and move topology current pointer."""
    topology = topology_service.get_by_id(topology_id, owner_id, session)
    current = resolve_current_diagram(
        topology.id,
        topology.current_diagram_id,
        session,
        get_diagram=diagram_repository.get_by_id,
    )
    if current is not None and data.base_diagram_version is not None and data.base_diagram_version != current.version:
        raise HTTPException(status_code=409, detail="Conflict: topology version is stale")

    draft = topology_personal_draft_repository.get_by_topology_and_user(session, topology.id, user_id)

    if data.cytoscape_json is not None:
        source_json = data.cytoscape_json
    elif draft is not None:
        source_json = draft.cytoscape_json
    elif current is not None:
        source_json = current.cytoscape_json
    else:
        source_json = empty_canvas_json()

    snapshot_name = resolve_snapshot_name(data.snapshot_name)
    now = utcnow()
    next_version = _next_immutable_diagram_version(current)
    diagram = DiagramLayout(
        name=snapshot_name,
        topology_id=topology.id,
        cytoscape_json=source_json,
        version=next_version,
    )

    try:
        saved_diagram = diagram_repository.create(session, diagram)
        history_entry = topology_history_repository.create(
            session,
            TopologyHistoryEntry(
                topology_id=topology.id,
                diagram_id=saved_diagram.id,
                snapshot_name=snapshot_name,
                action="save_version",
                created_by=user_id,
            ),
        )
        topology.current_diagram_id = saved_diagram.id
        topology.updated_at = now
        topology_repository.update(session, topology)
        if draft is not None:
            topology_personal_draft_repository.delete(session, draft)
        session.commit()
    except IntegrityError as exc:
        raise_conflict(exc, session, "Topology save version conflict")

    logger.info(
        "Topology version saved: topology_id={} history_entry_id={} diagram_id={}",
        topology.id,
        history_entry.id,
        saved_diagram.id,
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


def restore_history_entry(
    topology_id: uuid.UUID,
    history_entry_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    data: TopologyRestoreHistoryRequest,
    session: Session,
) -> TopologySaveVersionResponse:
    """Restore a history checkpoint as a new latest immutable version (append-only)."""
    topology = topology_service.get_by_id(topology_id, owner_id, session)
    current = resolve_current_diagram(
        topology.id,
        topology.current_diagram_id,
        session,
        get_diagram=diagram_repository.get_by_id,
    )
    if current is not None and data.base_diagram_version is not None and data.base_diagram_version != current.version:
        raise HTTPException(status_code=409, detail="Conflict: topology version is stale")

    history_entry = topology_history_repository.get_by_topology_and_id(
        session,
        topology.id,
        history_entry_id,
    )
    if history_entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")

    source_diagram = diagram_repository.get_by_id(session, history_entry.diagram_id)
    if source_diagram is None:
        raise HTTPException(status_code=404, detail="History snapshot not found")

    snapshot_name = resolve_snapshot_name(f"Restore of {history_entry.snapshot_name}")
    now = utcnow()
    next_version = _next_immutable_diagram_version(current)
    restored_diagram = DiagramLayout(
        name=snapshot_name,
        topology_id=topology.id,
        cytoscape_json=source_diagram.cytoscape_json,
        version=next_version,
    )

    try:
        saved_diagram = diagram_repository.create(session, restored_diagram)
        restore_entry = topology_history_repository.create(
            session,
            TopologyHistoryEntry(
                topology_id=topology.id,
                diagram_id=saved_diagram.id,
                snapshot_name=snapshot_name,
                action="restore",
                restored_from_history_entry_id=history_entry.id,
                created_by=user_id,
            ),
        )
        topology.current_diagram_id = saved_diagram.id
        topology.updated_at = now
        topology_repository.update(session, topology)
        draft = topology_personal_draft_repository.get_by_topology_and_user(session, topology.id, user_id)
        if draft is not None:
            topology_personal_draft_repository.delete(session, draft)
        session.commit()
    except IntegrityError as exc:
        raise_conflict(exc, session, "Topology restore conflict")

    logger.info(
        "Topology history restored: topology_id={} source_entry_id={} new_entry_id={}",
        topology.id,
        history_entry.id,
        restore_entry.id,
    )
    return TopologySaveVersionResponse(
        topology_id=topology.id,
        history_entry_id=restore_entry.id,
        current_diagram_id=saved_diagram.id,
        current_diagram_version=saved_diagram.version,
        snapshot_name=restore_entry.snapshot_name,
        action=restore_entry.action,
        restored_from_history_entry_id=history_entry.id,
        created_at=restore_entry.created_at,
        draft_version=None,
        has_unsaved_changes=False,
        cytoscape_json=with_ghost_contract(saved_diagram.cytoscape_json, topology.id, role, session),
    )

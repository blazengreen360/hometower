"""Topology editor state and personal draft service (HT-072)."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.topology_editor import TopologyEditorStateResponse
from src.models.topology_personal_draft import (
    TopologyPersonalDraftDiscardResponse,
    TopologyPersonalDraft,
    TopologyPersonalDraftSaveResponse,
    TopologyPersonalDraftUpsert,
)
from src.models.types import Role
from src.repositories import diagram_repository, topology_personal_draft_repository
from src.services import topology_service
from src.services.topology_editor_ghost_service import with_ghost_contract
from src.services.topology_editor_common import (
    clone_json,
    empty_canvas_json,
    has_unsaved_draft_changes,
    raise_conflict,
    resolve_current_diagram,
    utcnow,
)
from src.utils.logger import logger


def get_editor_state(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
    role: Role = Role.Reader,
) -> TopologyEditorStateResponse:
    """Return merged editor state from personal draft or current immutable history snapshot."""
    topology = topology_service.get_by_id(topology_id, owner_id, session)
    current = resolve_current_diagram(
        topology.id,
        topology.current_diagram_id,
        session,
        get_diagram=diagram_repository.get_by_id,
    )
    draft = topology_personal_draft_repository.get_by_topology_and_user(
        session,
        topology.id,
        user_id,
    )

    if draft is not None:
        has_unsaved_changes = has_unsaved_draft_changes(
            draft.cytoscape_json,
            current.cytoscape_json if current is not None else None,
        )
        return TopologyEditorStateResponse(
            topology_id=topology.id,
            current_diagram_id=current.id if current is not None else None,
            current_diagram_version=current.version if current is not None else None,
            draft_version=draft.version,
            has_unsaved_changes=has_unsaved_changes,
            source="draft",
            cytoscape_json=with_ghost_contract(draft.cytoscape_json, topology.id, role, session),
        )

    if current is not None:
        return TopologyEditorStateResponse(
            topology_id=topology.id,
            current_diagram_id=current.id,
            current_diagram_version=current.version,
            draft_version=None,
            has_unsaved_changes=False,
            source="history",
            cytoscape_json=with_ghost_contract(current.cytoscape_json, topology.id, role, session),
        )

    return TopologyEditorStateResponse(
        topology_id=topology.id,
        current_diagram_id=None,
        current_diagram_version=None,
        draft_version=None,
        has_unsaved_changes=False,
        source="empty",
        cytoscape_json=empty_canvas_json(),
    )


def save_personal_draft(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    data: TopologyPersonalDraftUpsert,
    session: Session,
) -> TopologyPersonalDraftSaveResponse:
    """Create or update the caller's personal draft for a topology."""
    topology = topology_service.get_by_id(topology_id, owner_id, session)
    current = resolve_current_diagram(
        topology.id,
        topology.current_diagram_id,
        session,
        get_diagram=diagram_repository.get_by_id,
    )
    draft = topology_personal_draft_repository.get_by_topology_and_user(
        session,
        topology.id,
        user_id,
    )

    try:
        if draft is None:
            draft = TopologyPersonalDraft(
                topology_id=topology.id,
                user_id=user_id,
                cytoscape_json=data.cytoscape_json,
                version=1,
            )
            result = topology_personal_draft_repository.create(session, draft)
        else:
            if data.base_version is not None and data.base_version != draft.version:
                raise HTTPException(
                    status_code=409,
                    detail="Conflict: personal draft was modified by another request",
                )
            draft.cytoscape_json = data.cytoscape_json
            draft.version += 1
            draft.updated_at = utcnow()
            result = topology_personal_draft_repository.update(session, draft)
        session.commit()
    except IntegrityError as exc:
        raise_conflict(exc, session, "Personal draft conflict")

    logger.info(
        "Topology personal draft saved: topology_id={} user_id={} version={}",
        topology.id,
        user_id,
        result.version,
    )
    has_unsaved_changes = has_unsaved_draft_changes(
        result.cytoscape_json,
        current.cytoscape_json if current is not None else None,
    )
    return TopologyPersonalDraftSaveResponse(
        topology_id=topology.id,
        version=result.version,
        has_unsaved_changes=has_unsaved_changes,
        updated_at=result.updated_at,
    )


def discard_personal_draft(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
) -> TopologyPersonalDraftDiscardResponse:
    """Delete the caller's personal draft for a topology if one exists."""
    topology = topology_service.get_by_id(topology_id, owner_id, session)
    draft = topology_personal_draft_repository.get_by_topology_and_user(
        session,
        topology.id,
        user_id,
    )

    discarded = False
    if draft is not None:
        try:
            topology_personal_draft_repository.delete(session, draft)
            session.commit()
            discarded = True
        except IntegrityError as exc:
            raise_conflict(exc, session, "Personal draft discard conflict")

    logger.info(
        "Topology personal draft discarded: topology_id={} user_id={} discarded={}",
        topology.id,
        user_id,
        discarded,
    )
    return TopologyPersonalDraftDiscardResponse(
        topology_id=topology.id,
        discarded=discarded,
        has_unsaved_changes=False,
    )

"""Facade for topology editor draft/history services (HT-072)."""
import uuid

from sqlmodel import Session

from src.models.topology_editor import (
    TopologyEditorStateResponse,
    TopologyRestoreHistoryRequest,
    TopologySaveVersionRequest,
    TopologySaveVersionResponse,
)
from src.models.types import Role
from src.models.topology_history_entry import PaginatedTopologyHistory
from src.models.topology_personal_draft import (
    TopologyPersonalDraftDiscardResponse,
    TopologyPersonalDraftSaveResponse,
    TopologyPersonalDraftUpsert,
)
from src.services import topology_editor_draft_service, topology_editor_history_service
from src.services import topology_editor_ghost_service


def get_editor_state(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    session: Session,
) -> TopologyEditorStateResponse:
    return topology_editor_draft_service.get_editor_state(
        topology_id=topology_id,
        owner_id=owner_id,
        user_id=user_id,
        role=role,
        session=session,
    )


def save_personal_draft(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    data: TopologyPersonalDraftUpsert,
    session: Session,
) -> TopologyPersonalDraftSaveResponse:
    return topology_editor_draft_service.save_personal_draft(
        topology_id=topology_id,
        owner_id=owner_id,
        user_id=user_id,
        data=data,
        session=session,
    )


def discard_personal_draft(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
) -> TopologyPersonalDraftDiscardResponse:
    return topology_editor_draft_service.discard_personal_draft(
        topology_id=topology_id,
        owner_id=owner_id,
        user_id=user_id,
        session=session,
    )


def list_history(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    session: Session,
    page: int = 1,
    limit: int = 50,
) -> PaginatedTopologyHistory:
    return topology_editor_history_service.list_history(
        topology_id=topology_id,
        owner_id=owner_id,
        session=session,
        page=page,
        limit=limit,
    )


def save_version(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    data: TopologySaveVersionRequest,
    session: Session,
) -> TopologySaveVersionResponse:
    return topology_editor_history_service.save_version(
        topology_id=topology_id,
        owner_id=owner_id,
        user_id=user_id,
        role=role,
        data=data,
        session=session,
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
    return topology_editor_history_service.restore_history_entry(
        topology_id=topology_id,
        history_entry_id=history_entry_id,
        owner_id=owner_id,
        user_id=user_id,
        role=role,
        data=data,
        session=session,
    )


def recreate_ghost_as_new_device(
    topology_id: uuid.UUID,
    ghost_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    base_diagram_version: int | None,
    session: Session,
) -> TopologySaveVersionResponse:
    return topology_editor_ghost_service.recreate_ghost_as_new_device(
        topology_id=topology_id,
        ghost_id=ghost_id,
        owner_id=owner_id,
        user_id=user_id,
        role=role,
        base_diagram_version=base_diagram_version,
        session=session,
    )


def map_ghost_to_existing_device(
    topology_id: uuid.UUID,
    ghost_id: uuid.UUID,
    live_device_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    base_diagram_version: int | None,
    session: Session,
) -> TopologySaveVersionResponse:
    return topology_editor_ghost_service.map_ghost_to_existing_device(
        topology_id=topology_id,
        ghost_id=ghost_id,
        live_device_id=live_device_id,
        owner_id=owner_id,
        user_id=user_id,
        role=role,
        base_diagram_version=base_diagram_version,
        session=session,
    )

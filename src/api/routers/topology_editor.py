"""Topology editor router for history checkpoints and personal drafts (HT-072)."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session, SQLModel

from src.api.dependencies.rbac import require_role
from src.models.topology_editor import (
    TopologyEditorStateResponse,
    TopologyRestoreHistoryRequest,
    TopologySaveVersionRequest,
    TopologySaveVersionResponse,
)
from src.models.topology_history_entry import PaginatedTopologyHistory
from src.models.topology_personal_draft import (
    TopologyPersonalDraftDiscardResponse,
    TopologyPersonalDraftSaveResponse,
    TopologyPersonalDraftUpsert,
)
from src.models.types import Role
from src.services import topology_editor_service
from src.utils.db import get_session

router = APIRouter(prefix="/topologies/{topology_id}", tags=["topology-editor"])


class TopologyGhostRecreateRequest(SQLModel):
    base_diagram_version: int | None = None


class TopologyGhostMapRequest(SQLModel):
    live_device_id: uuid.UUID
    base_diagram_version: int | None = None


def _request_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


def _request_role(request: Request) -> Role:
    return Role(request.state.role)


@router.get(
    "/editor-state",
    response_model=TopologyEditorStateResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_editor_state(
    topology_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologyEditorStateResponse:
    """Return topology-centric editor state using personal draft fallback semantics."""
    user_id = _request_user_id(request)
    return topology_editor_service.get_editor_state(
        topology_id=topology_id,
        owner_id=user_id,
        user_id=user_id,
        role=_request_role(request),
        session=session,
    )


@router.get(
    "/history",
    response_model=PaginatedTopologyHistory,
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_topology_history(
    topology_id: uuid.UUID,
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> PaginatedTopologyHistory:
    """Return immutable topology history entries."""
    user_id = _request_user_id(request)
    return topology_editor_service.list_history(
        topology_id=topology_id,
        owner_id=user_id,
        session=session,
        page=page,
        limit=limit,
    )


@router.put(
    "/personal-draft",
    response_model=TopologyPersonalDraftSaveResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def save_personal_draft(
    topology_id: uuid.UUID,
    data: TopologyPersonalDraftUpsert,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologyPersonalDraftSaveResponse:
    """Upsert the caller's personal draft for the topology."""
    user_id = _request_user_id(request)
    return topology_editor_service.save_personal_draft(
        topology_id=topology_id,
        owner_id=user_id,
        user_id=user_id,
        data=data,
        session=session,
    )


@router.delete(
    "/personal-draft",
    response_model=TopologyPersonalDraftDiscardResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def discard_personal_draft(
    topology_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologyPersonalDraftDiscardResponse:
    """Discard the caller's personal draft for the topology."""
    user_id = _request_user_id(request)
    return topology_editor_service.discard_personal_draft(
        topology_id=topology_id,
        owner_id=user_id,
        user_id=user_id,
        session=session,
    )


@router.post(
    "/save-version",
    response_model=TopologySaveVersionResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def save_topology_version(
    topology_id: uuid.UUID,
    data: TopologySaveVersionRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologySaveVersionResponse:
    """Create an immutable topology history version and advance current pointer."""
    user_id = _request_user_id(request)
    return topology_editor_service.save_version(
        topology_id=topology_id,
        owner_id=user_id,
        user_id=user_id,
        role=_request_role(request),
        data=data,
        session=session,
    )


@router.post(
    "/history/{history_entry_id}/restore",
    response_model=TopologySaveVersionResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def restore_topology_history(
    topology_id: uuid.UUID,
    history_entry_id: uuid.UUID,
    data: TopologyRestoreHistoryRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologySaveVersionResponse:
    """Restore a topology history entry append-only as a new latest version."""
    user_id = _request_user_id(request)
    return topology_editor_service.restore_history_entry(
        topology_id=topology_id,
        history_entry_id=history_entry_id,
        owner_id=user_id,
        user_id=user_id,
        role=_request_role(request),
        data=data,
        session=session,
    )


@router.post(
    "/ghosts/{ghost_id}/recreate",
    response_model=TopologySaveVersionResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def recreate_ghost_as_new_device(
    topology_id: uuid.UUID,
    ghost_id: uuid.UUID,
    data: TopologyGhostRecreateRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologySaveVersionResponse:
    """Recreate a deleted ghost placeholder as a new planned inventory device."""
    user_id = _request_user_id(request)
    return topology_editor_service.recreate_ghost_as_new_device(
        topology_id=topology_id,
        ghost_id=ghost_id,
        owner_id=user_id,
        user_id=user_id,
        role=_request_role(request),
        base_diagram_version=data.base_diagram_version,
        session=session,
    )


@router.post(
    "/ghosts/{ghost_id}/map",
    response_model=TopologySaveVersionResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def map_ghost_to_existing_device(
    topology_id: uuid.UUID,
    ghost_id: uuid.UUID,
    data: TopologyGhostMapRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologySaveVersionResponse:
    """Map a deleted ghost placeholder to an existing live inventory device."""
    user_id = _request_user_id(request)
    return topology_editor_service.map_ghost_to_existing_device(
        topology_id=topology_id,
        ghost_id=ghost_id,
        live_device_id=data.live_device_id,
        owner_id=user_id,
        user_id=user_id,
        role=_request_role(request),
        base_diagram_version=data.base_diagram_version,
        session=session,
    )

"""Workspaces router — CRUD endpoints for the Workspace entity."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.types import Role
from src.models.workspace import (
    PaginatedWorkspaceSummary,
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from src.services import workspace_service
from src.utils.db import get_session

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _owner_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


@router.get(
    "/",
    response_model=PaginatedWorkspaceSummary,
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_workspaces(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    session: Session = Depends(get_session),
) -> PaginatedWorkspaceSummary:
    """List caller's workspaces. Auto-creates default if none exist."""
    return workspace_service.list_summaries(
        _owner_id(request), session, page, limit, search=search,
    )


@router.post(
    "/",
    status_code=201,
    response_model=WorkspaceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_workspace(
    request: Request,
    data: WorkspaceCreate,
    session: Session = Depends(get_session),
) -> WorkspaceResponse:
    """Create a new workspace."""
    return workspace_service.create_response(_owner_id(request), data, session)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_workspace(
    workspace_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> WorkspaceResponse:
    """Get a workspace by ID."""
    return workspace_service.get_response(workspace_id, _owner_id(request), session)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def rename_workspace(
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> WorkspaceResponse:
    """Rename a workspace."""
    return workspace_service.rename_response(
        workspace_id, _owner_id(request), data, session,
    )


@router.delete(
    "/{workspace_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Admin))],
)
def delete_workspace(
    workspace_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Delete a workspace (CASCADE handles topologies and views)."""
    workspace_service.delete(workspace_id, _owner_id(request), session)

"""Topologies router — nested + standalone CRUD endpoints."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.topology import (
    PaginatedTopologySummary,
    TopologyCreate,
    TopologyResponse,
    TopologyUpdate,
)
from src.models.types import Role
from src.services import topology_service
from src.utils.db import get_session

nested_router = APIRouter(
    prefix="/workspaces/{workspace_id}/topologies", tags=["topologies"]
)
standalone_router = APIRouter(prefix="/topologies", tags=["topologies"])


def _owner_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


# --- Nested routes (under workspace) ---


@nested_router.get(
    "/",
    response_model=PaginatedTopologySummary,
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_topologies(
    workspace_id: uuid.UUID,
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> PaginatedTopologySummary:
    """List topologies in a workspace."""
    return topology_service.list_summaries(
        workspace_id, _owner_id(request), session, page, limit,
    )


@nested_router.post(
    "/",
    status_code=201,
    response_model=TopologyResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_topology(
    workspace_id: uuid.UUID,
    data: TopologyCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologyResponse:
    """Create a topology in a workspace."""
    return topology_service.create_response(
        workspace_id, _owner_id(request), data, session,
    )


# --- Standalone routes ---


@standalone_router.get(
    "/{topology_id}",
    response_model=TopologyResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_topology(
    topology_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologyResponse:
    """Get a topology by ID."""
    return topology_service.get_response(topology_id, _owner_id(request), session)


@standalone_router.patch(
    "/{topology_id}",
    response_model=TopologyResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def rename_topology(
    topology_id: uuid.UUID,
    data: TopologyUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> TopologyResponse:
    """Rename / update tags on a topology."""
    return topology_service.rename_response(
        topology_id, _owner_id(request), data, session,
    )


@standalone_router.delete(
    "/{topology_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Admin))],
)
def delete_topology(
    topology_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Delete a topology (CASCADE handles views)."""
    topology_service.delete(topology_id, _owner_id(request), session)

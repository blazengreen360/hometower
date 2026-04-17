"""Views router — list/create views under a topology.

A "View" is a DiagramLayout scoped to a Topology. Individual view
CRUD (get/patch/put/delete) uses the existing /api/diagrams/{id} endpoints.
"""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.diagram import (
    DiagramLayoutCreate,
    DiagramLayoutResponse,
    DiagramLayoutSummary,
    PaginatedDiagramSummary,
)
from src.models.types import Role
from src.services import diagram_service, topology_service
from src.utils.db import get_session

router = APIRouter(
    prefix="/topologies/{topology_id}/views", tags=["views"]
)


def _owner_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


@router.get(
    "/",
    response_model=PaginatedDiagramSummary,
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_views(
    topology_id: uuid.UUID,
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> PaginatedDiagramSummary:
    """List views (diagram layouts) in a topology."""
    topology_service.get_by_id(topology_id, _owner_id(request), session)
    items, total = diagram_service.get_by_topology(topology_id, session, page, limit)
    summaries = [
        DiagramLayoutSummary(
            id=layout.id,
            name=layout.name,
            topology_id=layout.topology_id,
            created_at=layout.created_at,
            updated_at=layout.updated_at,
        )
        for layout in items
    ]
    return PaginatedDiagramSummary(items=summaries, total=total, page=page, limit=limit)


@router.post(
    "/",
    status_code=201,
    response_model=DiagramLayoutResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_view(
    topology_id: uuid.UUID,
    data: DiagramLayoutCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> DiagramLayoutResponse:
    """Create a view (diagram layout) under a topology."""
    owner_id = _owner_id(request)
    topology_service.get_by_id(topology_id, owner_id, session)
    data.topology_id = topology_id
    layout = diagram_service.create(data, owner_id, session)
    return DiagramLayoutResponse(
        id=layout.id,
        name=layout.name,
        cytoscape_json=layout.cytoscape_json,
        topology_id=layout.topology_id,
        version=layout.version,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )

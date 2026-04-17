"""Diagrams router — CRUD endpoints for the DiagramLayout entity."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.diagram import (
    DiagramLayoutCreate,
    DiagramLayoutResponse,
    DiagramLayoutUpdate,
    PaginatedDiagramSummary,
    DiagramLayoutSummary,
)
from src.models.types import Role
from src.services import diagram_service
from src.utils.db import get_session

router = APIRouter(prefix="/diagrams", tags=["diagrams"])


def _owner_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


@router.get(
    "/",
    response_model=PaginatedDiagramSummary,
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_diagrams(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    topology_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
) -> PaginatedDiagramSummary:
    """List diagram layout summaries (no cytoscape_json). Requires Reader role."""
    owner_id = _owner_id(request)
    if topology_id is not None:
        items, total = diagram_service.get_by_topology(
            topology_id,
            session,
            page=page,
            limit=limit,
            owner_id=owner_id,
        )
    else:
        items, total = diagram_service.get_all(
            session,
            page=page,
            limit=limit,
            owner_id=owner_id,
        )
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
def create_diagram(
    data: DiagramLayoutCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> DiagramLayoutResponse:
    """Save a diagram layout. Requires Contributor role."""
    layout = diagram_service.create(data, _owner_id(request), session)
    return DiagramLayoutResponse(
        id=layout.id,
        name=layout.name,
        cytoscape_json=layout.cytoscape_json,
        topology_id=layout.topology_id,
        version=layout.version,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


@router.patch(
    "/{diagram_id}",
    response_model=DiagramLayoutResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def patch_diagram(
    diagram_id: uuid.UUID,
    data: DiagramLayoutUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> DiagramLayoutResponse:
    """Partially update a diagram layout. Requires Contributor role."""
    layout = diagram_service.partial_update(diagram_id, data, _owner_id(request), session)
    return DiagramLayoutResponse(
        id=layout.id,
        name=layout.name,
        cytoscape_json=layout.cytoscape_json,
        topology_id=layout.topology_id,
        version=layout.version,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


@router.put(
    "/{diagram_id}",
    response_model=DiagramLayoutResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def update_diagram(
    diagram_id: uuid.UUID,
    data: DiagramLayoutCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> DiagramLayoutResponse:
    """Update a diagram layout by ID. Requires Contributor role."""
    layout = diagram_service.update(diagram_id, data, _owner_id(request), session)
    return DiagramLayoutResponse(
        id=layout.id,
        name=layout.name,
        cytoscape_json=layout.cytoscape_json,
        topology_id=layout.topology_id,
        version=layout.version,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


@router.get(
    "/{diagram_id}",
    response_model=DiagramLayoutResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_diagram(
    diagram_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> DiagramLayoutResponse:
    """Get a diagram layout by ID with full cytoscape_json. Requires Reader role."""
    layout = diagram_service.get_by_id(diagram_id, session, owner_id=_owner_id(request))
    return DiagramLayoutResponse(
        id=layout.id,
        name=layout.name,
        cytoscape_json=layout.cytoscape_json,
        topology_id=layout.topology_id,
        version=layout.version,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


@router.delete(
    "/{diagram_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_diagram(
    diagram_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Delete a diagram layout. Requires Contributor role."""
    diagram_service.delete(diagram_id, _owner_id(request), session)

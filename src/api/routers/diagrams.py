"""Diagrams router — CRUD endpoints for the DiagramLayout entity."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from src.domain.rbac import require_role
from src.models.diagram import (
    DiagramLayoutCreate,
    DiagramLayoutResponse,
    PaginatedDiagramSummary,
    DiagramLayoutSummary,
)
from src.models.types import Role
from src.services import diagram_service
from src.utils.db import get_session

router = APIRouter(prefix="/diagrams", tags=["diagrams"])


@router.get(
    "/",
    response_model=PaginatedDiagramSummary,
    dependencies=[Depends(require_role(Role.Reader))],
)
async def list_diagrams(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> PaginatedDiagramSummary:
    """List diagram layout summaries (no cytoscape_json). Requires Reader role."""
    items, total = diagram_service.get_all(session, page=page, limit=limit)
    summaries = [
        DiagramLayoutSummary(
            id=layout.id,
            name=layout.name,
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
async def create_diagram(
    data: DiagramLayoutCreate,
    session: Session = Depends(get_session),
) -> DiagramLayoutResponse:
    """Save a diagram layout. Requires Contributor role."""
    layout = diagram_service.create(data, session)
    return DiagramLayoutResponse(
        id=layout.id,
        name=layout.name,
        cytoscape_json=layout.cytoscape_json,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


@router.get(
    "/{diagram_id}",
    response_model=DiagramLayoutResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
async def get_diagram(
    diagram_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> DiagramLayoutResponse:
    """Get a diagram layout by ID with full cytoscape_json. Requires Reader role."""
    layout = diagram_service.get_by_id(diagram_id, session)
    return DiagramLayoutResponse(
        id=layout.id,
        name=layout.name,
        cytoscape_json=layout.cytoscape_json,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


@router.delete(
    "/{diagram_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Admin))],
)
async def delete_diagram(
    diagram_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a diagram layout. Requires Admin role."""
    diagram_service.delete(diagram_id, session)

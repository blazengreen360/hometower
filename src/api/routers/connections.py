"""Connections router — CRUD endpoints for the Connection entity."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, SQLModel

from src.domain.rbac import require_role
from src.models.connection import ConnectionCreate, ConnectionResponse, ConnectionUpdate
from src.models.types import Role
from src.services import connection_service
from src.utils.db import get_session

router = APIRouter(prefix="/connections", tags=["connections"])


class PaginatedConnectionResponse(SQLModel):
    items: list[ConnectionResponse]
    total: int
    page: int
    limit: int


@router.get(
    "/",
    response_model=PaginatedConnectionResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
async def list_connections(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    source_id: Optional[uuid.UUID] = Query(default=None),
    target_id: Optional[uuid.UUID] = Query(default=None),
    session: Session = Depends(get_session),
) -> PaginatedConnectionResponse:
    """List connections with optional filters and pagination. Requires Reader role."""
    items, total = connection_service.get_all(session, page, limit, source_id, target_id)
    return PaginatedConnectionResponse(
        items=[ConnectionResponse.model_validate(c.model_dump()) for c in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/",
    status_code=201,
    response_model=ConnectionResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
async def create_connection(
    data: ConnectionCreate,
    session: Session = Depends(get_session),
) -> ConnectionResponse:
    """Create a new connection. Requires Contributor role."""
    conn = connection_service.create(data, session)
    return ConnectionResponse.model_validate(conn.model_dump())


@router.get(
    "/{connection_id}",
    response_model=ConnectionResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
async def get_connection(
    connection_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ConnectionResponse:
    """Get a connection by ID. Requires Reader role."""
    conn = connection_service.get_by_id(connection_id, session)
    return ConnectionResponse.model_validate(conn.model_dump())


@router.patch(
    "/{connection_id}",
    response_model=ConnectionResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
async def update_connection(
    connection_id: uuid.UUID,
    data: ConnectionUpdate,
    session: Session = Depends(get_session),
) -> ConnectionResponse:
    """Partially update a connection. Requires Contributor role."""
    conn = connection_service.update(connection_id, data, session)
    return ConnectionResponse.model_validate(conn.model_dump())


@router.delete(
    "/{connection_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
async def delete_connection(
    connection_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a connection. Requires Contributor role."""
    connection_service.delete(connection_id, session)

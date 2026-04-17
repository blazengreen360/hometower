"""Networks router — CRUD and enriched read endpoints for networks."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.network import (
    NetworkCreate,
    NetworkListResponse,
    NetworkResponse,
    NetworkResponseEnriched,
    NetworkUpdate,
)
from src.models.types import Role
from src.services import network_service
from src.utils.db import get_session

router = APIRouter(prefix="/networks", tags=["networks"])


@router.get(
    "/",
    response_model=list[NetworkListResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_networks(session: Session = Depends(get_session)) -> list[NetworkListResponse]:
    """List networks with attached device counts."""
    return network_service.get_all(session)


@router.post(
    "/",
    status_code=201,
    response_model=NetworkResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_network(
    data: NetworkCreate,
    session: Session = Depends(get_session),
) -> NetworkResponse:
    """Create a network. Requires Contributor role."""
    try:
        network = network_service.create(data, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return NetworkResponse.model_validate(network.model_dump())


@router.get(
    "/{network_id}",
    response_model=NetworkResponse | NetworkResponseEnriched,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_network(
    network_id: uuid.UUID,
    include: str = Query(default=""),
    session: Session = Depends(get_session),
) -> NetworkResponse | NetworkResponseEnriched:
    """Get a network by id. Pass ?include=devices for membership details."""
    include_set: set[str] = {k.strip() for k in include.split(",") if k.strip()}
    return network_service.get_by_id_enriched(network_id, include_set, session)


@router.patch(
    "/{network_id}",
    response_model=NetworkResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def update_network(
    network_id: uuid.UUID,
    data: NetworkUpdate,
    session: Session = Depends(get_session),
) -> NetworkResponse:
    """Update a network. Requires Contributor role."""
    try:
        network = network_service.update(network_id, data, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return NetworkResponse.model_validate(network.model_dump())


@router.delete(
    "/{network_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_network(
    network_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a network. Requires Contributor role."""
    network_service.delete(network_id, session)

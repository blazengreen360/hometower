"""Services router — CRUD endpoints for the Service entity (HT-023)."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.service import (
    DependencyRef,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
    ServiceWithDependencies,
)
from src.models.service_dependency import DependencyCreate
from src.models.types import Role
from src.services import service_service
from src.utils.db import get_session

router = APIRouter(prefix="/services", tags=["services"])


@router.get(
    "/",
    response_model=list[ServiceListResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_services(
    q: str | None = Query(default=None, max_length=255),
    session: Session = Depends(get_session),
) -> list[ServiceListResponse]:
    """List all services across all devices, with optional name filter."""
    return service_service.get_all(q, session)


@router.get(
    "/{service_id}",
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_service(
    service_id: uuid.UUID,
    include: str = Query(default=""),
    session: Session = Depends(get_session),
) -> ServiceWithDependencies | ServiceResponse:
    """Get a service by ID. Pass ?include=dependencies to enrich with dependency graph."""
    include_set: set[str] = {k.strip() for k in include.split(",") if k.strip()}
    if "dependencies" in include_set:
        return service_service.get_with_dependencies(service_id, session)
    svc = service_service.get_by_id(service_id, session)
    return ServiceResponse.model_validate(svc.model_dump())


@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def update_service(
    service_id: uuid.UUID,
    data: ServiceUpdate,
    session: Session = Depends(get_session),
) -> ServiceResponse:
    """Partially update a service. Requires Contributor role."""
    svc = service_service.update(service_id, data, session)
    return ServiceResponse.model_validate(svc.model_dump())


@router.delete(
    "/{service_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_service(
    service_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a service. Requires Contributor role."""
    service_service.delete(service_id, session)


@router.get(
    "/{service_id}/dependencies",
    response_model=list[DependencyRef],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_service_dependencies(
    service_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[DependencyRef]:
    """List dependency references for a service."""
    enriched = service_service.get_with_dependencies(service_id, session)
    return enriched.depends_on


@router.post(
    "/{service_id}/dependencies",
    status_code=201,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def add_service_dependency(
    service_id: uuid.UUID,
    data: DependencyCreate,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Add a dependency edge to a service. Requires Contributor role."""
    service_service.add_dependency(service_id, data.depends_on, session)
    return {"detail": "Dependency added"}


@router.delete(
    "/{service_id}/dependencies/{dep_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def remove_service_dependency(
    service_id: uuid.UUID,
    dep_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Remove a dependency edge from a service. Requires Contributor role."""
    service_service.remove_dependency(service_id, dep_id, session)

"""Service-entity service — orchestrates domain + repository (HT-023)."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import services as service_domain
from src.models.service import (
    DependencyRef,
    Service,
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
    ServiceWithDependencies,
)
from src.models.service_dependency import ServiceDependency
from src.repositories import device_repository, service_repository
from src.utils.logger import logger


def _assert_device_exists(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    if device_repository.get_by_id(session, device_id, owner_id=owner_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")


def _get_service_or_404(
    service_id: uuid.UUID,
    session: Session,
    detail: str = "Service not found",
) -> Service:
    service = service_repository.get_by_id(session, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail=detail)
    return service


def _validate_dependency_creation(
    service_id: uuid.UUID,
    depends_on_id: uuid.UUID,
    session: Session,
) -> None:
    _get_service_or_404(service_id, session)
    _get_service_or_404(depends_on_id, session, detail="Dependency service not found")

    if service_repository.dependency_exists(session, service_id, depends_on_id):
        raise HTTPException(status_code=409, detail="Dependency already exists")

    all_deps = service_repository.get_all_dependency_edges(session)
    try:
        service_domain.validate_no_dependency_cycle(service_id, depends_on_id, all_deps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _raise_add_dependency_integrity_error(
    exc: IntegrityError,
    session: Session,
) -> None:
    session.rollback()
    detail = str(exc.orig).lower() if exc.orig is not None else str(exc).lower()
    if "ck_service_dep_no_self_ref" in detail or "check constraint" in detail:
        raise HTTPException(
            status_code=400,
            detail="A service cannot depend on itself",
        ) from exc
    if "unique" in detail or "primary key" in detail:
        raise HTTPException(status_code=409, detail="Dependency already exists") from exc
    logger.exception("Unmapped IntegrityError in add_dependency")
    raise HTTPException(status_code=500, detail="Internal database error") from exc


def create(
    device_id: uuid.UUID,
    data: ServiceCreate,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> Service:
    """Validate and persist a new service on a device."""
    _assert_device_exists(device_id, session, owner_id=owner_id)
    try:
        service_domain.validate_port(data.port)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing = service_repository.get_by_device_and_name(session, device_id, data.name)
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Service name already exists on this device"
        )
    service = Service(
        device_id=device_id,
        name=data.name,
        port=data.port,
        protocol=data.protocol,
        url=data.url,
        status=data.status,
        notes=data.notes,
    )
    try:
        result = service_repository.create(session, service)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Service name already exists on this device"
        )
    logger.info("Service created: id={} device_id={} name={}", result.id, device_id, result.name)
    return result


def get_by_id(service_id: uuid.UUID, session: Session) -> Service:
    """Return service or raise HTTP 404."""
    return _get_service_or_404(service_id, session)


def get_by_device(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[ServiceResponse]:
    """Return all services for a device as response models."""
    _assert_device_exists(device_id, session, owner_id=owner_id)
    services = service_repository.get_by_device(session, device_id)
    return [ServiceResponse.model_validate(s.model_dump()) for s in services]


def get_all(q: str | None, session: Session) -> list[ServiceListResponse]:
    """Return flat list of all services across all devices, with device_name."""
    pairs = service_repository.get_all(session, q)
    return [
        ServiceListResponse.model_validate({**svc.model_dump(), "device_name": dev_name})
        for svc, dev_name in pairs
    ]


def update(service_id: uuid.UUID, data: ServiceUpdate, session: Session) -> Service:
    """Apply partial update to service fields."""
    svc = service_repository.get_by_id(session, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")
    update_data = data.model_dump(exclude_unset=True)
    if "port" in update_data:
        try:
            service_domain.validate_port(update_data["port"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "name" in update_data and update_data["name"].lower() != svc.name.lower():
        existing = service_repository.get_by_device_and_name(
            session, svc.device_id, update_data["name"]
        )
        if existing is not None:
            raise HTTPException(
                status_code=409, detail="Service already exists on this device"
            )
    for field, value in update_data.items():
        setattr(svc, field, value)
    try:
        result = service_repository.update(session, svc)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Service already exists on this device"
        ) from exc
    logger.info("Service updated: id={} name={}", result.id, result.name)
    return result


def delete(service_id: uuid.UUID, session: Session) -> None:
    """Delete service. Cascade in DB removes its dependencies."""
    svc = service_repository.get_by_id(session, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")
    service_repository.delete(session, svc)
    session.commit()
    logger.info("Service deleted: id={}", service_id)


def get_with_dependencies(
    service_id: uuid.UUID, session: Session
) -> ServiceWithDependencies:
    """Return service enriched with depends_on and depended_by lists."""
    svc = service_repository.get_by_id(session, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")
    fwd_edges = service_repository.get_dependency_edges_for_service(session, service_id)
    rev_edges = service_repository.get_reverse_dependency_edges(session, service_id)
    depends_on_list: list[DependencyRef] = []
    for edge in fwd_edges:
        dep_svc = service_repository.get_by_id(session, edge.depends_on_id)
        if dep_svc is not None:
            dev = device_repository.get_by_id(session, dep_svc.device_id)
            depends_on_list.append(DependencyRef(
                id=dep_svc.id,
                name=dep_svc.name,
                device_name=dev.name if dev else "",
            ))
    depended_by_list: list[DependencyRef] = []
    for edge in rev_edges:
        dep_svc = service_repository.get_by_id(session, edge.service_id)
        if dep_svc is not None:
            dev = device_repository.get_by_id(session, dep_svc.device_id)
            depended_by_list.append(DependencyRef(
                id=dep_svc.id,
                name=dep_svc.name,
                device_name=dev.name if dev else "",
            ))
    return ServiceWithDependencies(
        **svc.model_dump(),
        depends_on=depends_on_list,
        depended_by=depended_by_list,
    )


def add_dependency(
    service_id: uuid.UUID, depends_on_id: uuid.UUID, session: Session
) -> None:
    """Add a dependency edge. Validates no cycle before persisting."""
    _validate_dependency_creation(service_id, depends_on_id, session)
    dep = ServiceDependency(service_id=service_id, depends_on_id=depends_on_id)
    try:
        service_repository.add_dependency(session, dep)
        session.commit()
    except IntegrityError as exc:
        _raise_add_dependency_integrity_error(exc, session)
    logger.info("Service dependency added: {} -> {}", service_id, depends_on_id)


def remove_dependency(
    service_id: uuid.UUID, depends_on_id: uuid.UUID, session: Session
) -> None:
    """Remove a dependency edge. Raises HTTP 404 if edge does not exist."""
    if not service_repository.dependency_exists(session, service_id, depends_on_id):
        raise HTTPException(status_code=404, detail="Dependency not found")
    service_repository.remove_dependency(session, service_id, depends_on_id)
    session.commit()
    logger.info("Service dependency removed: {} -> {}", service_id, depends_on_id)

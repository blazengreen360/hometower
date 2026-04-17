"""Service repository (HT-023) — sole layer that holds SQLModel Session for Service ops."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, col, select
from sqlalchemy import select as sa_select

from src.models.device import Device
from src.models.service import Service
from src.models.service_dependency import ServiceDependency


def create(session: Session, service: Service) -> Service:
    """Persist a new service and return the refreshed instance."""
    session.add(service)
    session.flush()
    session.refresh(service)
    return service


def get_by_id(session: Session, service_id: uuid.UUID) -> Optional[Service]:
    """Return the service with the given primary key, or None."""
    return session.get(Service, service_id)


def get_by_device(session: Session, device_id: uuid.UUID) -> list[Service]:
    """Return all services for a device, ordered by name ASC."""
    stmt = (
        select(Service)
        .where(Service.device_id == device_id)
        .order_by(col(Service.name))
    )
    return list(session.exec(stmt).all())


def get_by_device_ids(
    session: Session, device_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Service]]:
    """Return services grouped by device_id for the provided device IDs."""
    if not device_ids:
        return {}
    grouped: dict[uuid.UUID, list[Service]] = {device_id: [] for device_id in device_ids}
    stmt = (
        select(Service)
        .where(col(Service.device_id).in_(device_ids))
        .order_by(col(Service.name))
    )
    rows = list(session.exec(stmt).all())
    for svc in rows:
        grouped[svc.device_id].append(svc)
    return grouped


def get_all(
    session: Session, q: Optional[str] = None
) -> list[tuple[Service, str]]:
    """Return (Service, device_name) pairs, optionally filtered by name substring."""
    stmt = (
        sa_select(Service, Device.name)  # type: ignore[call-overload]
        .join(Device, Service.device_id == Device.id)
        .order_by(col(Service.name))
    )
    if q:
        stmt = stmt.where(col(Service.name).ilike(f"%{q}%"))
    rows = list(session.execute(stmt).all())
    return [(row[0], row[1]) for row in rows]


def get_by_device_and_name(
    session: Session, device_id: uuid.UUID, name: str
) -> Optional[Service]:
    """Case-insensitive name lookup within a device (uniqueness guard)."""
    stmt = select(Service).where(
        Service.device_id == device_id,
        func.lower(Service.name) == name.lower(),
    )
    return session.exec(stmt).first()


def update(session: Session, service: Service) -> Service:
    """Persist changes to an already-fetched service and return it."""
    service.updated_at = datetime.now(timezone.utc)
    session.add(service)
    session.flush()
    session.refresh(service)
    return service


def delete(session: Session, service: Service) -> None:
    """Hard-delete a service (cascades to dependencies)."""
    session.delete(service)
    session.flush()


def add_dependency(session: Session, dep: ServiceDependency) -> ServiceDependency:
    """Persist a new service dependency edge."""
    session.add(dep)
    session.flush()
    session.refresh(dep)
    return dep


def get_dependency_edges_for_service(
    session: Session, service_id: uuid.UUID
) -> list[ServiceDependency]:
    """All edges WHERE service_id = service_id (what this service depends on)."""
    stmt = select(ServiceDependency).where(
        ServiceDependency.service_id == service_id
    )
    return list(session.exec(stmt).all())


def get_reverse_dependency_edges(
    session: Session, depends_on_id: uuid.UUID
) -> list[ServiceDependency]:
    """All edges WHERE depends_on_id = depends_on_id (what depends on this service)."""
    stmt = select(ServiceDependency).where(
        ServiceDependency.depends_on_id == depends_on_id
    )
    return list(session.exec(stmt).all())


def get_all_dependency_edges(
    session: Session,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Return all (service_id, depends_on_id) pairs — used for cycle detection."""
    rows = session.exec(
        select(ServiceDependency.service_id, ServiceDependency.depends_on_id)
    ).all()
    return [(r[0], r[1]) for r in rows]


def dependency_exists(
    session: Session, service_id: uuid.UUID, depends_on_id: uuid.UUID
) -> bool:
    """Return True if the dependency edge already exists."""
    dep = session.get(ServiceDependency, (service_id, depends_on_id))
    return dep is not None


def remove_dependency(
    session: Session, service_id: uuid.UUID, depends_on_id: uuid.UUID
) -> None:
    """Remove a dependency edge. No-op if it does not exist."""
    dep = session.get(ServiceDependency, (service_id, depends_on_id))
    if dep is not None:
        session.delete(dep)
        session.flush()

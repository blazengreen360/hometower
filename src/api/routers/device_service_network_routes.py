"""Device service and network sub-routes."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.device_network import (
    DeviceNetworkCreate,
    DeviceNetworkNetworkRef,
    DeviceNetworkResponse,
)
from src.models.service import ServiceCreate, ServiceResponse
from src.models.types import Role
from src.services import network_service, service_service
from src.utils.db import get_session

router = APIRouter()


def _owner_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


@router.get(
    "/{device_id}/services",
    response_model=list[ServiceResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_services(
    request: Request,
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ServiceResponse]:
    """Return all services for a device. Requires Reader role."""
    return service_service.get_by_device(device_id, session, owner_id=_owner_id(request))


@router.post(
    "/{device_id}/services",
    status_code=201,
    response_model=ServiceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_device_service(
    request: Request,
    device_id: uuid.UUID,
    data: ServiceCreate,
    session: Session = Depends(get_session),
) -> ServiceResponse:
    """Create a service on a device. Requires Contributor role."""
    svc = service_service.create(device_id, data, session, owner_id=_owner_id(request))
    return ServiceResponse.model_validate(svc.model_dump())


@router.get(
    "/{device_id}/networks",
    response_model=list[DeviceNetworkNetworkRef],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_networks(
    request: Request,
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[DeviceNetworkNetworkRef]:
    """Return all network memberships for a device."""
    return network_service.get_by_device(device_id, session, owner_id=_owner_id(request))


@router.post(
    "/{device_id}/networks",
    status_code=201,
    response_model=DeviceNetworkResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def attach_network_to_device(
    request: Request,
    device_id: uuid.UUID,
    data: DeviceNetworkCreate,
    session: Session = Depends(get_session),
) -> DeviceNetworkResponse:
    """Attach a network membership to a device."""
    membership = network_service.attach_to_device(
        device_id,
        data,
        session,
        owner_id=_owner_id(request),
    )
    return DeviceNetworkResponse(
        device_id=membership.device_id,
        network_id=membership.network_id,
        ip_address=membership.ip_address,
        created_at=membership.created_at,
    )


@router.delete(
    "/{device_id}/networks/{network_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def detach_network_from_device(
    request: Request,
    device_id: uuid.UUID,
    network_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Detach a device from a network membership."""
    network_service.detach_from_device(
        device_id,
        network_id,
        session,
        owner_id=_owner_id(request),
    )
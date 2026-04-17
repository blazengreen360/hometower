"""Device sub-routes — tags, custom fields, connections, and services endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel

from src.api.dependencies.rbac import require_role
from src.models.canvas_undo import (
    PublishedDeviceCanvasDeleteResult,
    PublishedDeviceCanvasRestoreResult,
    PublishedDeviceDeleteSnapshot,
)
from src.models.connection import ConnectionResponse
from src.models.custom_field import CustomFieldCreate, CustomFieldResponse, CustomFieldUpdate
from src.models.device_network import (
    DeviceNetworkCreate,
    DeviceNetworkNetworkRef,
    DeviceNetworkResponse,
)
from src.models.service import ServiceCreate, ServiceResponse
from src.models.tag import TagResponse
from src.models.types import Role
from src.services import (
    canvas_undo_service,
    connection_service,
    custom_field_service,
    network_service,
    service_service,
    tag_service,
)
from src.utils.db import get_session

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceTagAttach(SQLModel):
    tag_id: uuid.UUID


@router.get(
    "/{device_id}/tags",
    response_model=list[TagResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_tags(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[TagResponse]:
    """Return all tags attached to a device. Requires Reader role."""
    tags = tag_service.get_by_device(device_id, session)
    return [TagResponse.model_validate(t.model_dump()) for t in tags]


@router.post(
    "/{device_id}/tags",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def attach_tag_to_device(
    device_id: uuid.UUID,
    data: DeviceTagAttach,
    session: Session = Depends(get_session),
) -> None:
    """Attach a tag to a device (idempotent). Requires Contributor role."""
    tag_service.attach_to_device(device_id, data.tag_id, session)


@router.delete(
    "/{device_id}/tags/{tag_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def detach_tag_from_device(
    device_id: uuid.UUID,
    tag_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Detach a tag from a device. No-op if not attached. Requires Contributor role."""
    tag_service.detach_from_device(device_id, tag_id, session)


@router.get(
    "/{device_id}/custom-fields",
    response_model=list[CustomFieldResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_custom_fields(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[CustomFieldResponse]:
    """Return all custom fields for a device. Requires Reader role."""
    cfs = custom_field_service.get_by_device(device_id, session)
    return [CustomFieldResponse.model_validate(cf.model_dump()) for cf in cfs]


@router.post(
    "/{device_id}/custom-fields",
    status_code=201,
    response_model=CustomFieldResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_device_custom_field(
    device_id: uuid.UUID,
    data: CustomFieldCreate,
    session: Session = Depends(get_session),
) -> CustomFieldResponse:
    """Create a custom field for a device. Requires Contributor role."""
    cf = custom_field_service.create(device_id, data, session)
    return CustomFieldResponse.model_validate(cf.model_dump())


@router.patch(
    "/{device_id}/custom-fields/{cf_id}",
    response_model=CustomFieldResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def update_device_custom_field(
    device_id: uuid.UUID,
    cf_id: uuid.UUID,
    data: CustomFieldUpdate,
    session: Session = Depends(get_session),
) -> CustomFieldResponse:
    """Partially update a custom field. Requires Contributor role."""
    cf = custom_field_service.update(device_id, cf_id, data, session)
    return CustomFieldResponse.model_validate(cf.model_dump())


@router.delete(
    "/{device_id}/custom-fields/{cf_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_device_custom_field(
    device_id: uuid.UUID,
    cf_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a custom field. Requires Contributor role."""
    custom_field_service.delete(device_id, cf_id, session)


@router.get(
    "/{device_id}/connections",
    response_model=list[ConnectionResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_connections(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ConnectionResponse]:
    """Return all connections where the device is source or target. Requires Reader role."""
    conns = connection_service.get_connections_for_device(device_id, session)
    return [ConnectionResponse.model_validate(c.model_dump()) for c in conns]


@router.post(
    "/{device_id}/canvas-delete",
    response_model=PublishedDeviceCanvasDeleteResult,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def canvas_delete_device(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> PublishedDeviceCanvasDeleteResult:
    """Delete a published device through the canvas undo snapshot contract."""
    return canvas_undo_service.delete_published_device_for_canvas(device_id, session)


@router.post(
    "/{device_id}/restore",
    response_model=PublishedDeviceCanvasRestoreResult,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def restore_canvas_deleted_device(
    device_id: uuid.UUID,
    data: PublishedDeviceDeleteSnapshot,
    session: Session = Depends(get_session),
) -> PublishedDeviceCanvasRestoreResult:
    """Restore a published device previously deleted through canvas-delete."""
    if data.device.id != device_id:
        raise HTTPException(
            status_code=400,
            detail="Path device_id does not match snapshot device.id",
        )
    return canvas_undo_service.restore_published_device_for_canvas(data, session)


@router.get(
    "/{device_id}/services",
    response_model=list[ServiceResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_services(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ServiceResponse]:
    """Return all services for a device. Requires Reader role."""
    return service_service.get_by_device(device_id, session)


@router.post(
    "/{device_id}/services",
    status_code=201,
    response_model=ServiceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_device_service(
    device_id: uuid.UUID,
    data: ServiceCreate,
    session: Session = Depends(get_session),
) -> ServiceResponse:
    """Create a service on a device. Requires Contributor role."""
    svc = service_service.create(device_id, data, session)
    return ServiceResponse.model_validate(svc.model_dump())


@router.get(
    "/{device_id}/networks",
    response_model=list[DeviceNetworkNetworkRef],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_networks(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[DeviceNetworkNetworkRef]:
    """Return all network memberships for a device."""
    return network_service.get_by_device(device_id, session)


@router.post(
    "/{device_id}/networks",
    status_code=201,
    response_model=DeviceNetworkResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def attach_network_to_device(
    device_id: uuid.UUID,
    data: DeviceNetworkCreate,
    session: Session = Depends(get_session),
) -> DeviceNetworkResponse:
    """Attach a network membership to a device."""
    membership = network_service.attach_to_device(device_id, data, session)
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
    device_id: uuid.UUID,
    network_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Detach a device from a network membership."""
    network_service.detach_from_device(device_id, network_id, session)

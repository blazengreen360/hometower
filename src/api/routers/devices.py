"""Devices router — CRUD endpoints for the Device entity."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, SQLModel

from src.domain.rbac import require_role
from src.models.device import DeviceCreate, DeviceResponse, DeviceUpdate
from src.models.types import Role
from src.services import device_service
from src.utils.db import get_session

router = APIRouter(prefix="/devices", tags=["devices"])


class PaginatedDeviceResponse(SQLModel):
    items: list[DeviceResponse]
    total: int
    page: int
    limit: int


@router.post(
    "/",
    status_code=201,
    response_model=DeviceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
async def create_device(
    data: DeviceCreate,
    session: Session = Depends(get_session),
) -> DeviceResponse:
    """Create a new device. Requires Contributor role."""
    try:
        device = device_service.create(data, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DeviceResponse.model_validate(device.model_dump())


@router.get(
    "/",
    response_model=PaginatedDeviceResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
async def list_devices(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> PaginatedDeviceResponse:
    """List devices with pagination. Requires Reader role."""
    items, total = device_service.get_all(session, page, limit)
    return PaginatedDeviceResponse(
        items=[DeviceResponse.model_validate(d.model_dump()) for d in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{device_id}",
    response_model=DeviceResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
async def get_device(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> DeviceResponse:
    """Get a device by ID. Requires Reader role."""
    device = device_service.get_by_id(device_id, session)
    return DeviceResponse.model_validate(device.model_dump())


@router.patch(
    "/{device_id}",
    response_model=DeviceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
async def update_device(
    device_id: uuid.UUID,
    data: DeviceUpdate,
    session: Session = Depends(get_session),
) -> DeviceResponse:
    """Partially update a device. Requires Contributor role."""
    try:
        device = device_service.update(device_id, data, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DeviceResponse.model_validate(device.model_dump())


@router.delete(
    "/{device_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
async def delete_device(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a device. Requires Contributor role."""
    device_service.delete(device_id, session)

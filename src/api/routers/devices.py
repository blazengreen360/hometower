"""Devices router — CRUD endpoints for the Device entity."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, SQLModel

from src.api.dependencies.rbac import require_role
from src.models.device import (
    DeviceCreate,
    DevicePlacement,
    DeviceResponse,
    DeviceResponseEnriched,
    DeviceUpdate,
    PaginatedDeviceResponseEnriched,
)
from src.models.types import Role
from src.services import device_service
from src.utils.db import get_session

router = APIRouter(prefix="/devices", tags=["devices"])


def _owner_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


class PaginatedDeviceResponse(SQLModel):
    items: list[DeviceResponse]
    total: int
    page: int
    limit: int


@router.get(
    "/placed-ids",
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_placed_device_ids(
    request: Request,
    workspace_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[str]:
    """Return UUIDs of devices placed on at least one View. Requires Reader role."""
    placed = device_service.get_placed_device_ids(
        session,
        owner_id=_owner_id(request),
        workspace_id=workspace_id,
    )
    return [str(uid) for uid in placed]


@router.post(
    "/",
    status_code=201,
    response_model=DeviceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_device(
    data: DeviceCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> DeviceResponse:
    """Create a new device. Requires Contributor role."""
    try:
        device = device_service.create(data, _owner_id(request), session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DeviceResponse.model_validate(device.model_dump())


@router.get(
    "/",
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_devices(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=1000),
    include: str = Query(default=""),
    sort: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=500),
    workspace_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
) -> PaginatedDeviceResponseEnriched | PaginatedDeviceResponse:
    """List devices with pagination.

    Pass ?include=location,tags,services,networks to enrich with related data.
    Pass ?q=type:server to filter with structured search operators.
    Pass ?sort=name, ?sort=-name, ?sort=updated_at, etc. to control ordering.
    Invalid sort values are silently ignored.
    """
    include_set: set[str] = {k.strip() for k in include.split(",") if k.strip()}
    owner_id = _owner_id(request)
    if include_set or q:
        items, total = device_service.get_all_enriched(
            session,
            page,
            limit,
            include_set,
            q=q,
            sort=sort,
            workspace_id=workspace_id,
            owner_id=owner_id,
        )
        return PaginatedDeviceResponseEnriched(
            items=items, total=total, page=page, limit=limit
        )
    raw, total = device_service.get_all(
        session,
        page,
        limit,
        sort=sort,
        workspace_id=workspace_id,
        owner_id=owner_id,
    )
    return PaginatedDeviceResponse(
        items=[DeviceResponse.model_validate(d.model_dump()) for d in raw],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{device_id}",
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_device(
    request: Request,
    device_id: uuid.UUID,
    include: str = Query(default=""),
    session: Session = Depends(get_session),
) -> DeviceResponseEnriched | DeviceResponse:
    """Get a device by ID. Pass ?include=tags,location,services,networks to enrich the response."""
    include_set: set[str] = {k.strip() for k in include.split(",") if k.strip()}
    if include_set:
        return device_service.get_by_id_enriched(
            device_id,
            session,
            include_set,
            owner_id=_owner_id(request),
        )
    device = device_service.get_by_id(
        device_id,
        session,
        owner_id=_owner_id(request),
    )
    return DeviceResponse.model_validate(device.model_dump())


@router.patch(
    "/{device_id}",
    response_model=DeviceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def update_device(
    request: Request,
    device_id: uuid.UUID,
    data: DeviceUpdate,
    session: Session = Depends(get_session),
) -> DeviceResponse:
    """Partially update a device. Requires Contributor role."""
    try:
        device = device_service.update(
            device_id,
            data,
            session,
            owner_id=_owner_id(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DeviceResponse.model_validate(device.model_dump())


@router.get(
    "/{device_id}/placements",
    response_model=list[DevicePlacement],
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_device_placements(
    request: Request,
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[DevicePlacement]:
    """Return Views that contain this device. Requires Reader role."""
    owner_id = _owner_id(request)
    # Verify the device exists
    device_service.get_by_id(device_id, session, owner_id=owner_id)
    return device_service.get_device_placements(device_id, session, owner_id=owner_id)


@router.delete(
    "/{device_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_device(
    request: Request,
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a device. Requires Contributor role."""
    device_service.delete(device_id, session, owner_id=_owner_id(request))

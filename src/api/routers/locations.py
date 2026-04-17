"""Locations router — CRUD endpoints for the Location entity."""
import uuid
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import SQLModel, Session

from src.api.dependencies.rbac import require_role
from src.models.location import (
    LocationCreate,
    LocationResponse,
    LocationResponseWithAncestors,
    LocationUpdate,
)
from src.models.types import DeviceStatus, DeviceType, LocationType, Role
from src.services import location_service
from src.utils.db import get_session

router = APIRouter(prefix="/locations", tags=["locations"])


class LocationMapDeviceResponse(SQLModel):
    id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus


class LocationMapResponse(SQLModel):
    id: uuid.UUID
    name: str
    type: LocationType
    lat: float
    lng: float
    device_count: int
    devices: list[LocationMapDeviceResponse]


@router.post(
    "/",
    status_code=201,
    response_model=LocationResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_location(
    data: LocationCreate,
    session: Session = Depends(get_session),
) -> LocationResponse:
    """Create a new location. Requires Contributor role."""
    try:
        location = location_service.create(data, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return LocationResponse.model_validate(location.model_dump())


@router.get(
    "/",
    response_model=list[LocationMapResponse] | list[LocationResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_locations(
    type: LocationType | None = Query(default=None),
    include: str = Query(default=""),
    session: Session = Depends(get_session),
) -> list[LocationMapResponse] | list[LocationResponse]:
    """List all locations, optionally filtered by type. Requires Reader role."""
    include_set: set[str] = {k.strip() for k in include.split(",") if k.strip()}
    if "devices" in include_set:
        map_data = location_service.get_all_with_devices(session, type)
        return [LocationMapResponse.model_validate(item) for item in map_data]
    return location_service.get_all(session, type)


@router.get(
    "/{location_id}",
    response_model=Union[LocationResponse, LocationResponseWithAncestors],
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_location(
    location_id: uuid.UUID,
    include: str = Query(default=""),
    session: Session = Depends(get_session),
) -> Union[LocationResponse, LocationResponseWithAncestors]:
    """Get a location by ID. Pass ?include=ancestors to include ancestor chain.
    Requires Reader role.
    """
    if "ancestors" in include:
        return location_service.get_with_ancestors(location_id, session)
    return location_service.get_by_id(location_id, session)


@router.patch(
    "/{location_id}",
    response_model=LocationResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def update_location(
    location_id: uuid.UUID,
    data: LocationUpdate,
    session: Session = Depends(get_session),
) -> LocationResponse:
    """Partially update a location. Requires Contributor role."""
    try:
        return location_service.update(location_id, data, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/{location_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_location(
    location_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a location. Requires Contributor role."""
    location_service.delete(location_id, session)

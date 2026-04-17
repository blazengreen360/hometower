"""Location service — orchestrates domain logic and location repository."""
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import locations as locations_domain
from src.models.location import (
    Location,
    LocationCreate,
    LocationResponse,
    LocationResponseWithAncestors,
    LocationUpdate,
)
from src.models.types import DeviceStatus, DeviceType, LocationType
from src.repositories import location_repository
from src.utils.logger import logger


class LocationMapDeviceSummary(TypedDict):
    id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus


class LocationMapEntry(TypedDict):
    id: uuid.UUID
    name: str
    type: LocationType
    lat: float
    lng: float
    device_count: int
    devices: list[LocationMapDeviceSummary]


def _raise_location_conflict(exc: IntegrityError, session: Session) -> None:
    """Rollback failed writes and return a consistent conflict response."""
    session.rollback()
    raise HTTPException(status_code=409, detail="Location update conflict") from exc


def _validate_rack_row(location_type: LocationType, row: str | None) -> None:
    """Validate rack row constraints against effective entity state."""
    if location_type != LocationType.rack or row is None:
        return
    stripped = row.strip()
    if stripped == "":
        raise HTTPException(status_code=422, detail="row must not be empty")
    if stripped.startswith("-") and stripped[1:].isdigit():
        raise HTTPException(status_code=422, detail="row must be non-negative")


def create(data: LocationCreate, session: Session) -> Location:
    """Validate and persist a new location."""
    try:
        locations_domain.validate_location_fields(
            data.type, data.lat, data.lng, data.rack, data.row
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if data.parent_id is not None:
        parent = location_repository.get_by_id(session, data.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent location not found")

    location = Location(
        name=data.name,
        type=data.type,
        lat=data.lat,
        lng=data.lng,
        rack=data.rack,
        row=data.row,
        parent_id=data.parent_id,
    )
    result = location_repository.create(session, location)
    session.commit()
    logger.info("Location created: id={} name={}", result.id, result.name)
    return result


def get_by_id(location_id: uuid.UUID, session: Session) -> LocationResponse:
    """Return the location response or raise HTTP 404."""
    location = location_repository.get_by_id(session, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationResponse.model_validate(location.model_dump())


def get_all(
    session: Session, type: LocationType | None = None
) -> list[LocationResponse]:
    """Return all locations, optionally filtered by type."""
    locations = location_repository.get_all(session, type)
    return [LocationResponse.model_validate(loc.model_dump()) for loc in locations]


def get_all_with_devices(
    session: Session,
    type: LocationType | None = None,
) -> list[LocationMapEntry]:
    """Return geo locations with embedded device summaries for map consumers."""
    locations = location_repository.get_all(session, type)
    map_entries: list[LocationMapEntry] = []

    for location in locations:
        if location.type != LocationType.geo:
            continue
        if location.lat is None or location.lng is None:
            logger.warning(
                "Skipping geo location without coordinates: id={} name={}",
                location.id,
                location.name,
            )
            continue

        devices = location_repository.get_devices_at_location(session, location.id)
        device_summaries: list[LocationMapDeviceSummary] = sorted(
            [
                {
                    "id": device.id,
                    "name": device.name,
                    "type": device.type,
                    "status": device.status,
                }
                for device in devices
            ],
            key=lambda item: item["name"].lower(),
        )

        map_entries.append(
            {
                "id": location.id,
                "name": location.name,
                "type": location.type,
                "lat": location.lat,
                "lng": location.lng,
                "device_count": len(device_summaries),
                "devices": device_summaries,
            }
        )

    map_entries.sort(key=lambda item: item["name"].lower())
    return map_entries


def get_with_ancestors(
    location_id: uuid.UUID, session: Session
) -> LocationResponseWithAncestors:
    """Return the location with its ancestor chain (nearest→root)."""
    location = location_repository.get_by_id(session, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    try:
        ancestors = location_repository.get_ancestors(session, location_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ancestor_responses = [
        LocationResponse.model_validate(a.model_dump()) for a in ancestors
    ]
    return LocationResponseWithAncestors(
        **location.model_dump(), ancestors=ancestor_responses
    )


def update(
    location_id: uuid.UUID, data: LocationUpdate, session: Session
) -> LocationResponse:
    """Partially update a location; re-validate type consistency and cycle safety."""
    location = location_repository.get_by_id(session, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    update_data = data.model_dump(exclude_unset=True)

    # Compute merged effective values for validation
    effective_type = update_data.get("type", location.type)
    effective_lat = update_data.get("lat", location.lat)
    effective_lng = update_data.get("lng", location.lng)
    effective_rack = update_data.get("rack", location.rack)
    effective_row = update_data.get("row", location.row)

    try:
        locations_domain.validate_location_fields(
            effective_type, effective_lat, effective_lng, effective_rack, effective_row
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _validate_rack_row(effective_type, effective_row)

    if "parent_id" in update_data and update_data["parent_id"] != location.parent_id:
        new_parent_id = update_data["parent_id"]
        if new_parent_id is not None:
            parent = location_repository.get_by_id(session, new_parent_id)
            if parent is None:
                raise HTTPException(status_code=404, detail="Parent location not found")

            parent_map = location_repository.get_parent_map(session)
            if locations_domain.detect_cycle(location_id, new_parent_id, parent_map):
                raise HTTPException(
                    status_code=400, detail="Cycle detected in location hierarchy"
                )

    for field, value in update_data.items():
        setattr(location, field, value)

    location.updated_at = datetime.now(timezone.utc)
    try:
        result = location_repository.update(session, location)
        session.commit()
    except IntegrityError as exc:
        _raise_location_conflict(exc, session)
    logger.info("Location updated: id={} name={}", result.id, result.name)
    return LocationResponse.model_validate(result.model_dump())


def delete(location_id: uuid.UUID, session: Session) -> None:
    """Delete a location; raise 400 if devices are assigned, 404 if not found."""
    location = location_repository.get_by_id(session, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    children = location_repository.get_children(session, location_id)
    if children:
        raise HTTPException(
            status_code=400,
            detail="Location has child locations. Reassign or delete them first.",
        )

    devices = location_repository.get_devices_at_location(session, location_id)
    try:
        locations_domain.validate_location_deletable([d.name for d in devices])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    location_repository.delete(session, location)
    session.commit()
    logger.info("Location deleted: id={}", location_id)
